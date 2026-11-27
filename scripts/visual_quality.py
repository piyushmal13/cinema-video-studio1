from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any


def audit_visual_plan(scenes: list[dict[str, Any]], public_dir: str | Path = "public") -> dict[str, Any]:
    root = Path(public_dir)
    errors: list[str] = []
    warnings: list[str] = []
    queries = [str(scene.get("visualQuery", "")).strip().casefold() for scene in scenes]
    duplicate_queries = sorted({query for query in queries if query and queries.count(query) > 1})
    if duplicate_queries:
        warnings.append(f"Repeated visual queries were found: {len(duplicate_queries)}")
    files = [
        str(scene.get("mediaFile", "")).strip()
        for scene in scenes
        if scene.get("mediaFile") and scene.get("mediaKind") in {"image", "video"}
    ]
    if scenes and len(files) / len(scenes) < 0.60:
        warnings.append("Fewer than 60% of scenes have downloaded/generated media; some procedural fallbacks may appear.")
    hashes: dict[str, list[str]] = {}
    for relative in files:
        path = root / Path(*relative.replace("\\", "/").split("/"))
        if not path.is_file():
            warnings.append(f"Scene media is missing: {relative}")
            continue
        try:
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            hashes.setdefault(digest, []).append(relative)
        except OSError as error:
            warnings.append(f"Could not inspect scene media {relative}: {error}")
    duplicates = [paths for paths in hashes.values() if len(paths) > 1]
    if duplicates:
        warnings.append(f"Duplicate media files are reused in {sum(len(group) for group in duplicates)} scene placements.")
    return {
        "passed": not errors,
        "scene_count": len(scenes),
        "media_backed_scenes": len(files),
        "warnings": warnings,
        "errors": errors,
    }


def audit_render(video_path: str | Path) -> dict[str, Any]:
    path = Path(video_path)
    if not path.is_file() or path.stat().st_size == 0:
        return {"passed": False, "errors": [f"Video output is missing: {path}"]}
    ffprobe = "ffprobe"
    try:
        result = subprocess.run(
            [ffprobe, "-v", "error", "-show_entries", "stream=codec_type,width,height",
             "-show_entries", "format=duration,size", "-of", "json", str(path)],
            check=True, capture_output=True, text=True, timeout=30,
        )
        probe = json.loads(result.stdout)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        return {"passed": False, "errors": [f"ffprobe verification failed: {error}"]}
    stream_types = {stream.get("codec_type") for stream in probe.get("streams", [])}
    duration = float(probe.get("format", {}).get("duration", 0.0) or 0.0)
    errors = []
    if not {"video", "audio"}.issubset(stream_types):
        errors.append(f"Expected video and audio streams, found: {stream_types}")
    if duration < 3:
        errors.append(f"Rendered video is unexpectedly short: {duration:.2f}s")
    return {
        "passed": not errors,
        "duration_sec": round(duration, 2),
        "size_bytes": path.stat().st_size,
        "streams": sorted(stream_types),
        "errors": errors,
    }
