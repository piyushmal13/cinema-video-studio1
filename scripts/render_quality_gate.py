#!/usr/bin/env python3
"""Fail a production when the MP4 is invalid or OCR finds overlapping text boxes."""
from __future__ import annotations

import argparse
import csv
import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

try:
    from .visual_quality import audit_render, audit_visual_plan
except ImportError:
    from visual_quality import audit_render, audit_visual_plan


def overlapping_boxes(rows: list[dict[str, Any]], threshold: float = 0.12) -> list[dict[str, Any]]:
    words = []
    for row in rows:
        if str(row.get("level", "")) != "5" or not str(row.get("text", "")).strip():
            continue
        try:
            left, top = int(row["left"]), int(row["top"])
            width, height = int(row["width"]), int(row["height"])
        except (KeyError, TypeError, ValueError):
            continue
        if width > 0 and height > 0:
            words.append((str(row["text"]).strip(), left, top, left + width, top + height))

    collisions = []
    for index, first in enumerate(words):
        for second in words[index + 1:]:
            x_overlap = max(0, min(first[3], second[3]) - max(first[1], second[1]))
            y_overlap = max(0, min(first[4], second[4]) - max(first[2], second[2]))
            intersection = x_overlap * y_overlap
            smaller_area = min(
                (first[3] - first[1]) * (first[4] - first[2]),
                (second[3] - second[1]) * (second[4] - second[2]),
            )
            if smaller_area and intersection / smaller_area >= threshold:
                collisions.append({"first": first[0], "second": second[0], "overlap_ratio": round(intersection / smaller_area, 3)})
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
            rows = list(csv.DictReader(result.stdout.splitlines(), delimiter="\t"))
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
    args = parser.parse_args()

    report = {"render": audit_render(args.video)}
    try:
        video_data = json.loads(Path(args.video_data).read_text(encoding="utf-8"))
        plan = audit_visual_plan(video_data.get("scenes", []), "public")
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
        report["plan"] = {**plan, "critical_warnings": critical, "passed": bool(plan.get("passed")) and not critical}
    except (OSError, ValueError, TypeError) as error:
        report["plan"] = {"passed": False, "errors": [f"Could not inspect storyboard data: {error}"]}
    if args.ocr:
        report["text_overlap"] = inspect_text_collisions(args.video)
    report["passed"] = bool(report["render"].get("passed")) and bool(report["plan"].get("passed")) and (
        not args.ocr or bool(report["text_overlap"].get("passed"))
    )
    target = Path(args.report)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
