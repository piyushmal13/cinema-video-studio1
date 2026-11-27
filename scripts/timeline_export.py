from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def export_otio(video_data: dict[str, Any], output_path: str | Path) -> bool:
    """Write an optional editorial timeline for NLE handoff; video rendering does not depend on OTIO."""
    try:
        import opentimelineio as otio
    except ImportError:
        return False

    fps = 30
    timeline = otio.schema.Timeline(name=str(video_data.get("title", "Cinema Studio")))
    video_track = otio.schema.Track(name="Picture", kind=otio.schema.TrackKind.Video)
    audio_track = otio.schema.Track(name="Voice and score", kind=otio.schema.TrackKind.Audio)

    for index, scene in enumerate(video_data.get("scenes", [])):
        start = max(0.0, float(scene.get("startSec", 0.0)))
        end = max(start, float(scene.get("endSec", start)))
        duration = otio.opentime.RationalTime((end - start) * fps, fps)
        media_file = str(scene.get("mediaFile", "")).strip()
        if media_file:
            url = media_file.replace("\\", "/")
            reference = otio.schema.ExternalReference(target_url=url)
        else:
            reference = otio.schema.GeneratorReference(
                generator_kind="cinema-studio-placeholder",
                parameters={"warning": "Visual asset was not attached to this timeline export"},
            )
        clip = otio.schema.Clip(name=f"{index + 1:02d} · {scene.get('headline', 'Scene')}", media_reference=reference)
        clip.source_range = otio.opentime.TimeRange(
            start_time=otio.opentime.RationalTime(0, fps), duration=duration
        )
        clip.metadata["cinema"] = {
            "visual_query": scene.get("visualQuery", ""),
            "kicker": scene.get("kicker", ""),
            "camera_motion": scene.get("cameraMotion", ""),
        }
        video_track.append(clip)

    timeline.tracks.append(video_track)
    audio_path = str(video_data.get("masterAudioFile") or video_data.get("voiceoverFile") or "")
    if audio_path:
        audio_clip = otio.schema.Clip(
            name="Master audio",
            media_reference=otio.schema.ExternalReference(target_url=audio_path),
        )
        audio_clip.source_range = otio.opentime.TimeRange(
            start_time=otio.opentime.RationalTime(0, fps),
            duration=otio.opentime.RationalTime(float(video_data.get("totalDurationSec", 0)) * fps, fps),
        )
        audio_track.append(audio_clip)
        timeline.tracks.append(audio_track)

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    otio.adapters.write_to_file(timeline, str(path))
    return path.is_file() and path.stat().st_size > 0
