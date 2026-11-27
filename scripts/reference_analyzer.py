#!/usr/bin/env python3
"""Extract an editorial style brief from user-provided reference media.

This is a deterministic, optional-dependency analyzer. It never downloads social
media URLs or republishes source media. Video files must be supplied locally.
"""
from __future__ import annotations

import argparse
import base64
import json
import math
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

try:
    import requests
except ImportError:  # vision analysis is optional
    requests = None


def _run(command: list[str], timeout: int = 90) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=True)
    except (OSError, subprocess.SubprocessError):
        return None


def probe_video(path: str | Path) -> dict[str, Any]:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return {"available": False, "reason": "ffprobe is not installed"}
    result = _run([
        ffprobe, "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=width,height,r_frame_rate,duration:format=duration",
        "-of", "json", str(path),
    ], timeout=20)
    if not result:
        return {"available": False, "reason": "ffprobe could not inspect the supplied video"}
    try:
        payload = json.loads(result.stdout)
        stream = (payload.get("streams") or [{}])[0]
        duration = float(stream.get("duration") or payload.get("format", {}).get("duration") or 0)
        width, height = int(stream.get("width") or 0), int(stream.get("height") or 0)
        fps_text = str(stream.get("r_frame_rate") or "0/1")
        numerator, denominator = (fps_text.split("/", 1) + ["1"])[:2]
        fps = float(numerator) / max(float(denominator), 1)
        return {
            "available": True, "duration_sec": round(duration, 3),
            "width": width, "height": height,
            "aspect_ratio": round(width / height, 4) if height else None,
            "fps": round(fps, 3),
            "orientation": "vertical" if height > width else "landscape" if width > height else "square",
        }
    except (ValueError, TypeError, KeyError, ZeroDivisionError):
        return {"available": False, "reason": "Video metadata was malformed"}


def detect_scene_cuts(path: str | Path, limit: int = 100) -> list[float]:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return []
    # showinfo emits timestamps for frames selected by FFmpeg's scene-change detector.
    result = _run([
        ffmpeg, "-hide_banner", "-i", str(path), "-vf",
        "select='gt(scene,0.28)',showinfo", "-vsync", "vfr",
        "-frames:v", str(max(1, min(limit, 200))), "-f", "null", "-",
    ], timeout=180)
    if not result:
        return []
    diagnostic = result.stderr or ""
    return [round(float(value), 3) for value in re.findall(r"pts_time:([0-9]+(?:\.[0-9]+)?)", diagnostic)[:limit]]


def extract_video_contact_sheet(path: str | Path, output_dir: str | Path, count: int = 8) -> list[str]:
    ffmpeg = shutil.which("ffmpeg")
    metadata = probe_video(path)
    duration = float(metadata.get("duration_sec") or 0)
    if not ffmpeg or duration <= 0:
        return []
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    outputs: list[str] = []
    for index in range(max(1, min(count, 12))):
        timestamp = duration * (index + 0.5) / max(1, min(count, 12))
        frame = target / f"reference_frame_{index + 1:02d}.jpg"
        result = _run([
            ffmpeg, "-y", "-ss", f"{timestamp:.3f}", "-i", str(path),
            "-frames:v", "1", "-vf", "scale=480:-2", "-q:v", "4", str(frame),
        ], timeout=30)
        if result and frame.is_file() and frame.stat().st_size:
            outputs.append(str(frame))
    return outputs


def _image_metadata(path: str | Path) -> dict[str, Any]:
    try:
        from PIL import Image, ImageStat
        image = Image.open(path).convert("RGB")
        width, height = image.size
        small = image.resize((1, 1))
        average = tuple(round(value) for value in small.getpixel((0, 0)))
        return {
            "path": str(path), "width": width, "height": height,
            "aspect_ratio": round(width / height, 4) if height else None,
            "average_rgb": list(average),
            "orientation": "portrait" if height > width else "landscape" if width > height else "square",
        }
    except (ImportError, OSError, ValueError):
        return {"path": str(path), "available": False, "reason": "Pillow is unavailable or image could not be decoded"}



def _gemini_image_description(path: str | Path) -> dict[str, Any] | None:
    """Use the already-configured Gemini API key for bounded multimodal reference analysis."""
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key or requests is None:
        return None
    model = os.environ.get("CINEMA_REFERENCE_VISION_MODEL") or os.environ.get("GEMINI_MODEL", "gemini-3.8-flash")
    try:
        from PIL import Image
        from io import BytesIO
        with Image.open(path) as source:
            image = source.convert("RGB")
            image.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
            buffer = BytesIO()
            image.save(buffer, format="JPEG", quality=82, optimize=True)
            encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    except (ImportError, OSError, ValueError):
        encoded = base64.b64encode(Path(path).read_bytes()).decode("ascii")
    prompt = (
        "Act as a professional visual editor analyzing a user-provided reference image. "
        "Return JSON only with subject, visible_objects, action, environment, composition, "
        "focal_point (normalized x and y numbers from 0 to 1), dominant_colors, visible_text, "
        "crop_warnings, and editing_notes. Identify important logos, product labels, faces, "
        "and text that must not be clipped. Do not infer identity or invent unseen details."
    )
    response = requests.post(
        "https://generativelanguage.googleapis.com/v1beta/models/" + model + ":generateContent",
        headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
        json={
            "contents": [{"role": "user", "parts": [
                {"text": prompt},
                {"inlineData": {"mimeType": "image/jpeg", "data": encoded}},
            ]}],
            "generationConfig": {"responseMimeType": "application/json", "maxOutputTokens": 900},
        },
        timeout=(10, 75),
    )
    if response.status_code != 200:
        return {"status": "unavailable", "reason": f"Gemini vision returned HTTP {response.status_code}"}
    try:
        raw = response.json()["candidates"][0]["content"]["parts"][0]["text"]
        fence = chr(96) * 3
        cleaned = str(raw).strip().removeprefix(fence + "json").removeprefix(fence).removesuffix(fence).strip()
        return json.loads(cleaned)
    except (ValueError, KeyError, IndexError, TypeError):
        return {"status": "unavailable", "reason": "Gemini vision did not return the required JSON shape"}


def _ollama_image_description(path: str | Path) -> dict[str, Any] | None:
    """Optional local vision model. No image leaves the machine unless the user configured a remote URL."""
    endpoint = os.environ.get("CINEMA_VISION_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
    model = os.environ.get("CINEMA_VISION_MODEL", "").strip()
    if not model or requests is None:
        return None
    try:
        encoded = base64.b64encode(Path(path).read_bytes()).decode("ascii")
        response = requests.post(
            f"{endpoint}/api/generate",
            json={
                "model": model,
                "prompt": (
                    "Describe this image for a professional video editor. Return concise JSON with "
                    "subject, visible_objects, action, environment, composition, focal_point, "
                    "dominant_colors, visible_text, crop_warnings, and focal_point as normalized x/y numbers from 0 to 1. "
                    "Do not invent unseen details."
                ),
                "images": [encoded], "stream": False, "format": "json",
            },
            timeout=(5, 90),
        )
        response.raise_for_status()
        body = response.json()
        raw = body.get("response", "")
        return json.loads(raw) if isinstance(raw, str) else raw
    except (OSError, ValueError, KeyError, requests.RequestException):
        return {"status": "unavailable", "reason": "Configured local vision model did not return valid JSON"}


def _focal_point_from_entropy(path: str | Path) -> tuple[float, float]:
    """Estimate a visually busy focal region; this is a crop heuristic, not semantic vision."""
    try:
        from PIL import Image, ImageStat
        image = Image.open(path).convert("L")
        width, height = image.size
        grid = []
        for gy in range(4):
            for gx in range(4):
                crop = image.crop((gx * width / 4, gy * height / 4, (gx + 1) * width / 4, (gy + 1) * height / 4))
                stat = ImageStat.Stat(crop)
                # Contrast/standard deviation as a lightweight saliency proxy.
                center_weight = 1.0 - 0.12 * (abs(gx - 1.5) + abs(gy - 1.5))
                grid.append((stat.stddev[0] * center_weight, gx, gy))
        _, gx, gy = max(grid)
        return ((gx + 0.5) / 4, (gy + 0.5) / 4)
    except (ImportError, OSError, ValueError):
        return (0.5, 0.5)


def smart_crop_image(
    source: str | Path, destination: str | Path,
    target_width: int = 1080, target_height: int = 1920,
    focal_x: float | None = None, focal_y: float | None = None,
) -> dict[str, Any]:
    """Crop to a target frame while retaining a supplied or estimated focal point."""
    try:
        from PIL import Image
    except ImportError:
        return {"ok": False, "reason": "Install Pillow to enable smart image fitting"}
    source_path, output_path = Path(source), Path(destination)
    try:
        image = Image.open(source_path).convert("RGB")
    except OSError as error:
        return {"ok": False, "reason": f"Could not open image: {error}"}
    width, height = image.size
    if width < 1 or height < 1 or target_width < 1 or target_height < 1:
        return {"ok": False, "reason": "Image and target dimensions must be positive"}
    if focal_x is None or focal_y is None:
        estimated_x, estimated_y = _focal_point_from_entropy(source_path)
        focal_x = estimated_x if focal_x is None else focal_x
        focal_y = estimated_y if focal_y is None else focal_y
    focal_x, focal_y = min(1.0, max(0.0, focal_x)), min(1.0, max(0.0, focal_y))
    target_ratio, source_ratio = target_width / target_height, width / height
    if source_ratio > target_ratio:
        crop_h, crop_w = height, int(round(height * target_ratio))
    else:
        crop_w, crop_h = width, int(round(width / target_ratio))
    center_x, center_y = focal_x * width, focal_y * height
    left = int(min(max(0, center_x - crop_w / 2), width - crop_w))
    top = int(min(max(0, center_y - crop_h / 2), height - crop_h))
    fitted = image.crop((left, top, left + crop_w, top + crop_h)).resize((target_width, target_height), Image.Resampling.LANCZOS)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fitted.save(output_path, quality=92, optimize=True)
    return {
        "ok": True, "source": str(source_path), "output": str(output_path),
        "source_size": [width, height], "target_size": [target_width, target_height],
        "crop_box": [left, top, left + crop_w, top + crop_h],
        "focal_point": [round(focal_x, 4), round(focal_y, 4)],
        "method": "explicit-or-entropy-heuristic",
    }


def build_style_brief(video_path: str | Path | None, image_paths: list[str], output_dir: str | Path) -> dict[str, Any]:
    report: dict[str, Any] = {
        "schema_version": 1,
        "analysis_mode": "reference_editorial_dna",
        "video": None,
        "scene_cuts_sec": [],
        "average_shot_length_sec": None,
        "reference_images": [],
        "editing_guidance": [],
        "limitations": [
            "A social reel URL is not downloaded or copied; provide a video file you have rights to use.",
            "Without a configured vision model, image descriptions are metadata and crop heuristics, not semantic understanding.",
            "Typography/OCR and exact style matching require a separate configured OCR/vision capability.",
        ],
    }
    if video_path:
        metadata = probe_video(video_path)
        report["video"] = metadata
        if metadata.get("available"):
            cuts = detect_scene_cuts(video_path)
            report["scene_cuts_sec"] = cuts
            duration = float(metadata.get("duration_sec") or 0)
            intervals = [b - a for a, b in zip([0.0, *cuts], [*cuts, duration]) if b > a]
            report["average_shot_length_sec"] = round(sum(intervals) / len(intervals), 3) if intervals else None
            report["contact_sheet_frames"] = extract_video_contact_sheet(video_path, output_dir, count=4)
    contact_frames = list(report.get("contact_sheet_frames") or [])
    for path in [*image_paths, *contact_frames]:
        metadata = _image_metadata(path)
        description = _gemini_image_description(path) or _ollama_image_description(path)
        if description:
            metadata["vision_description"] = description
        metadata["reference_role"] = "uploaded_image" if path in image_paths else "video_contact_sheet_frame"
        metadata["estimated_focal_point"] = list(_focal_point_from_entropy(path))
        report["reference_images"].append(metadata)
    if report["video"] and report["video"].get("available"):
        orientation = report["video"].get("orientation")
        pace = report.get("average_shot_length_sec")
        report["editing_guidance"].append(f"Reference frame orientation: {orientation}.")
        if pace:
            report["editing_guidance"].append(f"Reference average shot length: {pace:.2f}s; use as a pacing cue, not a rigid rule.")
    if report["reference_images"]:
        report["editing_guidance"].append("Use reference images as visual direction; do not stretch them. Fit each shot to the output frame with a focal-point-aware crop.")
    return report



def reference_prompt_context(report_path: str | Path) -> str:
    """Turn measured reference cues into concise, non-copying editorial instructions."""
    try:
        report = json.loads(Path(report_path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ""
    cues = []
    video = report.get("video") or {}
    if video.get("available"):
        cues.append(
            f"Reference editing grammar: {video.get('orientation')} {video.get('width')}x{video.get('height')}, "
            f"{video.get('duration_sec')} seconds."
        )
        pace = report.get("average_shot_length_sec")
        if pace:
            cues.append(f"Use approximately {pace:.2f}s average shot rhythm as a pacing reference, not a fixed template.")
        cuts = report.get("scene_cuts_sec") or []
        if cuts:
            cues.append(f"Reference contains about {len(cuts) + 1} detected shots; vary shot scale and transition timing.")
    for image in (report.get("reference_images") or [])[:5]:
        vision = image.get("vision_description")
        if isinstance(vision, dict):
            subject = vision.get("subject")
            composition = vision.get("composition")
            action = vision.get("action")
            visible_text = vision.get("visible_text")
            crop_warnings = vision.get("crop_warnings")
            if subject:
                cues.append(f"Supplied image subject: {subject}.")
            if composition:
                cues.append(f"Reference composition: {composition}.")
            if action:
                cues.append(f"Visible action: {action}.")
            if visible_text:
                cues.append(f"Preserve this visible text/branding: {visible_text}.")
            if crop_warnings:
                cues.append(f"Crop protection notes: {crop_warnings}.")
        elif image.get("orientation"):
            cues.append(f"Supplied reference image orientation: {image['orientation']}.")
    if cues:
        cues.append(
            "Use the references as original visual direction and supplied source assets; "
            "do not copy another creator's exact sequence, wording, footage or audio."
        )
    return "\n".join(cues)[:1800]


def prepare_reference_images(
    scenes: list[dict[str, Any]], manifest_path: str | Path,
    orientation: str, public_dir: str | Path = "public",
) -> dict[int, str]:
    """Fit a supplied image and assign it to the most relevant storyboard scene."""
    try:
        manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if manifest.get("kind") != "image" or not manifest.get("path"):
        return {}
    source = Path(str(manifest["path"]))
    if not source.is_file() or not scenes:
        return {}

    subject_text = ""
    focal_x = focal_y = None
    try:
        report = json.loads(Path("out/reference_style.json").read_text(encoding="utf-8"))
        image = (report.get("reference_images") or [{}])[0]
        vision = image.get("vision_description") or {}
        subject_text = " ".join(
            str(vision.get(key, "")) for key in ("subject", "visible_objects", "action")
        )
        focal = vision.get("focal_point")
        if isinstance(focal, dict):
            focal_x, focal_y = float(focal.get("x")), float(focal.get("y"))
        elif isinstance(focal, (list, tuple)) and len(focal) >= 2:
            focal_x, focal_y = float(focal[0]), float(focal[1])
        if focal_x is not None and not (0 <= focal_x <= 1 and 0 <= focal_y <= 1):
            focal_x = focal_y = None
    except (OSError, ValueError, TypeError, AttributeError):
        subject_text = ""
        focal_x = focal_y = None

    width, height = (1080, 1920) if orientation == "vertical" else (1920, 1080)
    target = Path(public_dir) / "media" / "user_reference_01.jpg"
    crop = smart_crop_image(source, target, width, height, focal_x, focal_y)
    if not crop.get("ok"):
        return {}

    tokens = {
        token.casefold() for token in re.findall(r"[A-Za-z0-9]{3,}", subject_text)
    }
    scores = []
    for index, scene in enumerate(scenes):
        scene_text = " ".join(
            str(scene.get(key, "")) for key in ("headline", "kicker", "visualQuery", "subline")
        )
        scene_tokens = {
            token.casefold() for token in re.findall(r"[A-Za-z0-9]{3,}", scene_text)
        }
        scores.append((len(tokens & scene_tokens), index))
    best_score, best_index = max(scores, default=(0, 0))
    if not best_score:
        best_index = 0
    return {best_index: str(target.relative_to(public_dir)).replace("\\", "/")}
def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", help="JSON manifest produced by fetch_telegram_reference.py")
    parser.add_argument("--video", help="Local reference video file; never a social URL")
    parser.add_argument("--images", nargs="*", default=[], help="Local reference image files")
    parser.add_argument("--output", default="out/reference_style.json")
    parser.add_argument("--contact-sheet-dir", default="out/reference_frames")
    parser.add_argument("--crop-to", choices=["vertical", "landscape", "square"])
    parser.add_argument("--crop-dir", default="out/reference_crops")
    args = parser.parse_args()
    video_path = args.video
    image_paths = list(args.images)
    if args.manifest:
        manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
        if not isinstance(manifest, dict):
            parser.error("Reference manifest must be a JSON object")
        if manifest.get("kind") == "video":
            video_path = manifest.get("path") or video_path
        elif manifest.get("kind") == "image":
            image_paths.append(str(manifest.get("path") or ""))
        else:
            parser.error("Reference manifest kind must be image or video")
    image_paths = [path for path in image_paths if path]
    if not video_path and not image_paths:
        parser.error("Supply --manifest, --video and/or one or more --images")
    report = build_style_brief(video_path, image_paths, args.contact_sheet_dir)
    if args.crop_to and image_paths:
        dimensions = {"vertical": (1080, 1920), "landscape": (1920, 1080), "square": (1080, 1080)}[args.crop_to]
        report["fitted_reference_images"] = [
            smart_crop_image(path, Path(args.crop_dir) / f"{Path(path).stem}_{args.crop_to}.jpg", *dimensions)
            for path in image_paths
        ]
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
