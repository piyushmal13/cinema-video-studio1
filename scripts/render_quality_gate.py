#!/usr/bin/env python3
"""Fail a production when its MP4, storyboard, media or rendered text is unsafe."""
from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

try:
    from .visual_quality import audit_render, audit_visual_plan
except ImportError:
    from visual_quality import audit_render, audit_visual_plan


_PUNCTUATION_ONLY = re.compile(r"^[\W_]+$", re.UNICODE)


def overlapping_boxes(rows: list[dict[str, Any]], threshold: float = 0.12) -> list[dict[str, Any]]:
    """Detect substantial word-box overlap while ignoring punctuation noise."""
    words = []
    for row in rows:
        if str(row.get("level", "")) != "5":
            continue
        text = str(row.get("text", "")).strip()
        if not text or _PUNCTUATION_ONLY.fullmatch(text):
            continue
        try:
            left, top = int(row["left"]), int(row["top"])
            width, height = int(row["width"]), int(row["height"])
        except (KeyError, TypeError, ValueError):
            continue
        if width > 0 and height > 0:
            words.append((text, left, top, left + width, top + height))

    # Tesseract can emit a second, single-letter token from inside a correctly
    # recognized word (for example "e" inside "Analysis"). These duplicate
    # glyph detections are not independent text elements and create false
    # collision reports. Keep standalone one-letter labels unless their center
    # is already covered by another multi-character word box.
    filtered_words = []
    for index, word in enumerate(words):
        text, left, top, right, bottom = word
        if len(text) == 1 and text.isalpha():
            center_x = (left + right) / 2
            center_y = (top + bottom) / 2
            duplicate_glyph = any(
                other_index != index
                and len(other[0]) > 1
                and other[1] <= center_x <= other[3]
                and other[2] <= center_y <= other[4]
                for other_index, other in enumerate(words)
            )
            if duplicate_glyph:
                continue
        filtered_words.append(word)

    collisions = []
    for index, first in enumerate(filtered_words):
        for second in filtered_words[index + 1:]:
            x_overlap = max(0, min(first[3], second[3]) - max(first[1], second[1]))
            y_overlap = max(0, min(first[4], second[4]) - max(first[2], second[2]))
            intersection = x_overlap * y_overlap
            smaller_area = min(
                (first[3] - first[1]) * (first[4] - first[2]),
                (second[3] - second[1]) * (second[4] - second[2]),
            )
            if smaller_area and intersection / smaller_area >= threshold:
                collisions.append({
                    "first": first[0],
                    "second": second[0],
                    "overlap_ratio": round(intersection / smaller_area, 3),
                })
    return collisions


def inspect_text_collisions(video_path: str | Path, sample_fps: float = 1.0) -> dict[str, Any]:
    ffmpeg = shutil.which("ffmpeg")
    tesseract = shutil.which("tesseract")
    if not ffmpeg or not tesseract:
        return {"available": False, "errors": ["OCR gate requires both FFmpeg and Tesseract."]}
    collisions = []
    sampled_frames = 0
    with tempfile.TemporaryDirectory(prefix="cinema-ocr-") as directory:
        pattern = str(Path(directory) / "frame-%04d.png")
        extracted = subprocess.run(
            [ffmpeg, "-hide_banner", "-loglevel", "error", "-i", str(video_path),
             "-vf", f"fps={sample_fps},scale=540:-1", "-frames:v", "180", pattern],
            capture_output=True, text=True, timeout=180,
        )
        if extracted.returncode != 0:
            return {"available": False, "errors": ["Could not extract frames for OCR inspection."]}
        for frame_path in sorted(Path(directory).glob("frame-*.png")):
            sampled_frames += 1
            result = subprocess.run(
                [tesseract, str(frame_path), "stdout", "tsv"],
                capture_output=True, text=True, timeout=20,
            )
            if result.returncode != 0:
                continue
            rows = list(csv.DictReader(result.stdout.splitlines(), delimiter="\\t"))
            for collision in overlapping_boxes(rows):
                collisions.append({"frame": frame_path.name, **collision})
    return {
        "available": True,
        "sampled_frames": sampled_frames,
        "collision_count": len(collisions),
        "collisions": collisions[:50],
        "passed": not collisions and sampled_frames > 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", default="out/final.mp4")
    parser.add_argument("--report", default="out/render_quality_report.json")
    parser.add_argument("--video-data", default="public/video_data.json")
    parser.add_argument("--ocr", action="store_true", help="Require OCR-based text-overlap inspection.")
    parser.add_argument(
        "--minimum-media-ratio",
        type=float,
        default=float(__import__("os").environ.get("CINEMA_MIN_MEDIA_RATIO", "0.60")),
        help="Minimum fraction of scenes backed by an actual image/video asset (default: 0.60).",
    )
    args = parser.parse_args()
    if not 0.0 <= args.minimum_media_ratio <= 1.0:
        parser.error("--minimum-media-ratio must be between 0 and 1.")

    report = {"render": audit_render(args.video)}
    try:
        video_data = json.loads(Path(args.video_data).read_text(encoding="utf-8"))
        plan = audit_visual_plan(
            video_data.get("scenes", []),
            "public",
            minimum_media_ratio=args.minimum_media_ratio,
            enforce_media_ratio=True,
        )
        if video_data.get("degradedMode"):
            plan.setdefault("errors", []).append(
                "Storyboard was generated in degraded mode because primary AI providers were unavailable."
            )
            plan["passed"] = False
        critical_markers = (
            "Scene media is missing:",
            "Duplicate media files are reused",
            "Repeated visual queries were found:",
            "Visual grammar is too narrow:",
            "Adjacent scenes repeat the same composition",
        )
        critical = [
            warning for warning in plan.get("warnings", [])
            if any(marker in warning for marker in critical_markers)
        ]
        report["plan"] = {
            **plan,
            "critical_warnings": critical,
            "passed": bool(plan.get("passed")) and not critical,
        }
    except (OSError, ValueError, TypeError) as error:
        report["plan"] = {"passed": False, "errors": [f"Could not inspect storyboard data: {error}"]}

    if args.ocr:
        report["text_overlap"] = inspect_text_collisions(args.video)
    report["passed"] = (
        bool(report["render"].get("passed"))
        and bool(report["plan"].get("passed"))
        and (not args.ocr or bool(report.get("text_overlap", {}).get("passed")))
    )
    target = Path(args.report)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
