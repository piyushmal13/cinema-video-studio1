from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any


def _has_valid_media_signature(path: Path) -> bool:
    """Reject non-media payloads before counting an asset as visual coverage."""
    try:
        with path.open("rb") as media_file:
            header = media_file.read(32)
    except OSError:
        return False
    suffix = path.suffix.lower()
    if suffix in {".jpg", ".jpeg"}:
        return header.startswith(b"\xff\xd8\xff")
    if suffix == ".png":
        return header.startswith(b"\x89PNG\r\n\\x1a\n")
    if suffix == ".webp":
        return header.startswith(b"RIFF") and b"WEBP" in header
    if suffix == ".mp4":
        return b"ftyp" in header
    return False


def audit_visual_plan(
    scenes: list[dict[str, Any]],
    public_dir: str | Path = "public",
    *,
    minimum_media_ratio: float = 0.60,
    enforce_media_ratio: bool = False,
) -> dict[str, Any]:
    """Audit the authored storyboard and its actual local media assignments.

    Kinetic type and deliberately data-led graphics may be media-free. The
    media coverage ratio therefore measures the whole film and is reported
    independently; CI can choose whether to enforce the configured threshold.
    """
    root = Path(public_dir)
    errors: list[str] = []
    warnings: list[str] = []
    queries = [
        str(scene.get("visualQuery", "")).strip().casefold()
        for scene in scenes if isinstance(scene, dict)
    ]
    duplicate_queries = sorted({query for query in queries if query and queries.count(query) > 1})
    if duplicate_queries:
        warnings.append(f"Repeated visual queries were found: {len(duplicate_queries)}")

    scene_media_files: list[tuple[int, list[str]]] = []
    intentionally_graphic_scenes = 0
    for index, scene in enumerate(scenes):
        if not isinstance(scene, dict):
            errors.append(f"Scene {index + 1} is not an object.")
            continue
        if scene.get("mediaMode") == "graphic" or scene.get("type") == "kinetic_type":
            intentionally_graphic_scenes += 1
        if scene.get("mediaKind") not in {"image", "video"}:
            continue
        scene_files: list[str] = []
        primary = scene.get("mediaFile")
        if isinstance(primary, str) and primary.strip():
            scene_files.append(primary.strip())
        sequence = scene.get("mediaFiles")
        if isinstance(sequence, list):
            scene_files.extend(item.strip() for item in sequence if isinstance(item, str) and item.strip())
        scene_media_files.append((index, list(dict.fromkeys(scene_files))))

    files: list[str] = []
    media_backed_scenes = 0
    missing_files: list[str] = []
    hashes: dict[str, list[str]] = {}
    for _scene_index, scene_files in scene_media_files:
        valid_scene_asset = False
        for relative in scene_files:
            normalized = relative.replace("\\", "/")
            path = (root / Path(*normalized.split("/"))).resolve()
            try:
                path.relative_to(root.resolve())
            except ValueError:
                errors.append(f"Scene media path escapes the public directory: {relative}")
                continue
            if not path.is_file() or path.stat().st_size <= 0 or not _has_valid_media_signature(path):
                missing_files.append(relative)
                continue
            valid_scene_asset = True
            files.append(relative)
            try:
                digest = hashlib.sha256(path.read_bytes()).hexdigest()
                hashes.setdefault(digest, []).append(relative)
            except OSError as error:
                warnings.append(f"Could not inspect scene media {relative}: {error}")
        if valid_scene_asset:
            media_backed_scenes += 1

    media_ratio = media_backed_scenes / len(scenes) if scenes else 0.0
    if scenes and media_ratio < minimum_media_ratio:
        message = (
            f"Media coverage is {media_backed_scenes}/{len(scenes)} scenes "
            f"({media_ratio:.0%}); required minimum is {minimum_media_ratio:.0%}."
        )
        (errors if enforce_media_ratio else warnings).append(message)

    treatments = [
        str(scene.get("visualTreatment", "")).strip()
        for scene in scenes if isinstance(scene, dict)
    ]
    treatments = [treatment for treatment in treatments if treatment]
    unique_treatments = sorted(set(treatments))
    adjacent_repeats = sum(left == right for left, right in zip(treatments, treatments[1:]))
    if len(scenes) >= 6 and len(unique_treatments) < min(5, len(scenes) // 2):
        warnings.append(
            f"Visual grammar is too narrow: {len(unique_treatments)} unique treatments "
            f"for {len(scenes)} scenes."
        )
    if adjacent_repeats:
        warnings.append(f"Adjacent scenes repeat the same composition {adjacent_repeats} time(s).")

    if missing_files:
        warnings.append(f"Scene media is missing: {', '.join(missing_files[:10])}")
    duplicates = [paths for paths in hashes.values() if len(paths) > 1]
    if duplicates:
        warnings.append(f"Duplicate media files are reused in {sum(len(group) for group in duplicates)} scene placements.")

    return {
        "passed": not errors,
        "scene_count": len(scenes),
        "media_backed_scenes": media_backed_scenes,
        "media_coverage_ratio": round(media_ratio, 3),
        "intentionally_graphic_scenes": intentionally_graphic_scenes,
        "visual_treatments": unique_treatments,
        "visual_treatment_count": len(unique_treatments),
        "adjacent_treatment_repeats": adjacent_repeats,
        "warnings": warnings,
        "errors": errors,
    }


def audit_render(video_path: str | Path) -> dict[str, Any]:
    path = Path(video_path)
    if not path.is_file() or path.stat().st_size == 0:
        return {"passed": False, "errors": [f"Video output is missing: {path}"], "warnings": []}
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return {
            "passed": False,
            "errors": ["ffprobe is not installed; rendered stream verification cannot run."],
            "warnings": [],
        }
    try:
        result = subprocess.run(
            [ffprobe, "-v", "error", "-show_entries", "stream=codec_type,width,height",
             "-show_entries", "format=duration,size", "-of", "json", str(path)],
            check=True, capture_output=True, text=True, timeout=30,
        )
        probe = json.loads(result.stdout)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        return {
            "passed": False,
            "errors": [f"ffprobe verification failed: {error}"],
            "warnings": [],
        }

    stream_types = {stream.get("codec_type") for stream in probe.get("streams", [])}
    duration = float(probe.get("format", {}).get("duration", 0.0) or 0.0)
    errors: list[str] = []
    warnings: list[str] = []
    if not {"video", "audio"}.issubset(stream_types):
        errors.append(f"Expected video and audio streams, found: {stream_types}")
    if duration < 3:
        errors.append(f"Rendered video is unexpectedly short: {duration:.2f}s")

    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg and duration >= 3:
        try:
            scan = subprocess.run(
                [ffmpeg, "-hide_banner", "-i", str(path),
                 "-vf", "blackdetect=d=0.8:pix_th=0.12,freezedetect=n=-55dB:d=3",
                 "-an", "-f", "null", "-"],
                check=False, capture_output=True, text=True, timeout=90,
            )
            diagnostic = (scan.stderr or "") + (scan.stdout or "")
            black_events = len(re.findall(r"black_start:", diagnostic))
            freeze_events = len(re.findall(r"freeze_start:", diagnostic))
            if black_events:
                warnings.append(
                    f"FFmpeg detected {black_events} black intervals of at least 0.8 seconds; review intentional fades versus blank frames."
                )
            if freeze_events:
                warnings.append(
                    f"FFmpeg detected {freeze_events} possible frozen intervals of at least 3 seconds; review static shots."
                )
            if scan.returncode not in {0, 255}:
                warnings.append("FFmpeg artifact scan could not complete.")
        except (OSError, subprocess.SubprocessError) as error:
            warnings.append(f"FFmpeg artifact scan unavailable: {error}")

    return {
        "passed": not errors,
        "duration_sec": round(duration, 2),
        "size_bytes": path.stat().st_size,
        "streams": sorted(stream_types),
        "errors": errors,
        "warnings": warnings,
    }
