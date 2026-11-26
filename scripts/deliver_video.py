from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Callable

import requests


TELEGRAM_VIDEO_LIMIT = 50_000_000
UPLOAD_TARGET_BYTES = 47 * 1024 * 1024
MAX_UPLOAD_ATTEMPTS = 3


def _probe_video(ffprobe: str | None, video_path: Path) -> tuple[float, int, int]:
    if ffprobe:
        result = subprocess.run(
            [
                ffprobe,
                "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=width,height:format=duration",
                "-of", "json",
                str(video_path),
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        metadata = json.loads(result.stdout)
        streams = metadata.get("streams", [])
        if not streams:
            raise RuntimeError("The rendered MP4 contains no video stream.")
        width = int(streams[0]["width"])
        height = int(streams[0]["height"])
        duration = float(metadata["format"]["duration"])
    else:
        import imageio_ffmpeg

        reader = imageio_ffmpeg.read_frames(str(video_path), pix_fmt="rgb24")
        try:
            metadata = next(reader)
        except StopIteration as error:
            raise RuntimeError("The rendered MP4 contains no video frames.") from error
        finally:
            reader.close()
        width, height = metadata["size"]
        duration = float(metadata["duration"])
    if width <= 0 or height <= 0 or not math.isfinite(duration) or duration <= 0:
        raise RuntimeError("The rendered MP4 has invalid video dimensions or duration.")
    return duration, width, height


def _encode_under_limit(
    source: Path,
    destination: Path,
    target_bytes: int,
    ffmpeg: str,
    ffprobe: str | None,
) -> Path:
    duration, width, height = _probe_video(ffprobe, source)
    landscape = width >= height
    max_width, max_height = (1280, 720) if landscape else (720, 1280)
    total_kbps = int((target_bytes * 8 / duration / 1000) * 0.94)
    video_kbps = min(8000, total_kbps - 112)
    if video_kbps < 128:
        raise RuntimeError(
            "The video is too long to fit Telegram's 50 MB upload limit at a "
            "watchable bitrate."
        )

    last_size = 0
    for attempt in range(MAX_UPLOAD_ATTEMPTS):
        bitrate = max(128, int(video_kbps * (0.78**attempt)))
        subprocess.run(
            [
                ffmpeg, "-y",
                "-i", str(source),
                "-map", "0:v:0",
                "-map", "0:a:0?",
                "-vf",
                f"scale={max_width}:{max_height}:"
                "force_original_aspect_ratio=decrease:force_divisible_by=2",
                "-c:v", "libx264",
                "-preset", "veryfast",
                "-b:v", f"{bitrate}k",
                "-maxrate", f"{int(bitrate * 1.1)}k",
                "-bufsize", f"{bitrate * 2}k",
                "-pix_fmt", "yuv420p",
                "-c:a", "aac",
                "-b:a", "96k",
                "-movflags", "+faststart",
                "-threads", "2",
                "-f", "mp4",
                str(destination),
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=max(180, int(duration * 4)),
        )
        last_size = destination.stat().st_size
        if last_size <= target_bytes:
            print(
                f"Compressed video to {last_size / (1024 * 1024):.1f} MiB "
                f"({max_width}x{max_height} maximum)."
            )
            return destination
        destination.unlink(missing_ok=True)

    raise RuntimeError(
        f"FFmpeg could not fit the video under the {target_bytes}-byte upload "
        f"target; last attempt was {last_size} bytes."
    )


def deliver_video(
    video_path: str | Path,
    bot_token: str,
    chat_id: str,
    *,
    ffmpeg: str | None = None,
    ffprobe: str | None = None,
    post: Callable = requests.post,
) -> None:
    source = Path(video_path)
    if not bot_token or not chat_id:
        raise ValueError("TELEGRAM_BOT_TOKEN and Telegram chat ID are required.")
    if not source.is_file() or source.stat().st_size == 0:
        raise FileNotFoundError(f"Rendered video is missing or empty: {source}")

    ffmpeg = ffmpeg or shutil.which("ffmpeg")
    ffprobe = ffprobe or shutil.which("ffprobe")
    upload_limit = min(UPLOAD_TARGET_BYTES, TELEGRAM_VIDEO_LIMIT - 1_000_000)
    force_compress = source.stat().st_size > upload_limit
    target_bytes = upload_limit
    last_description = "Telegram rejected the video."
    url = f"https://api.telegram.org/bot{bot_token}/sendVideo"

    with tempfile.TemporaryDirectory(prefix="cinema-telegram-") as temp_name:
        compressed_path = Path(temp_name) / "telegram-ready.mp4"
        for attempt in range(MAX_UPLOAD_ATTEMPTS):
            upload_path = source
            if force_compress:
                if not ffmpeg:
                    raise RuntimeError(
                        "FFmpeg is required to compress this video "
                        "for Telegram's 50 MB upload limit."
                    )
                upload_path = _encode_under_limit(
                    source,
                    compressed_path,
                    target_bytes,
                    ffmpeg,
                    ffprobe,
                )

            with upload_path.open("rb") as video_file:
                response = post(
                    url,
                    data={
                        "chat_id": chat_id,
                        "caption": "Your finished cinema film is ready.",
                        "supports_streaming": "true",
                    },
                    files={"video": (upload_path.name, video_file, "video/mp4")},
                    timeout=(15, 300),
                )

            try:
                result = response.json()
            except ValueError:
                result = {}

            if response.status_code == 413 or (
                response.status_code >= 400
                and "request entity too large" in str(result).lower()
            ):
                last_description = "Telegram returned HTTP 413 (file too large)."
                force_compress = True
                target_bytes = min(target_bytes, int(target_bytes * 0.82))
                if attempt < MAX_UPLOAD_ATTEMPTS - 1:
                    continue
                break

            if response.status_code >= 400:
                description = (
                    result.get("description")
                    if isinstance(result, dict)
                    else None
                )
                raise RuntimeError(
                    f"Telegram sendVideo failed with HTTP {response.status_code}"
                    + (f": {description}" if description else ".")
                )
            if not isinstance(result, dict) or result.get("ok") is not True:
                description = (
                    result.get("description")
                    if isinstance(result, dict)
                    else None
                )
                raise RuntimeError(
                    "Telegram did not confirm delivery"
                    + (f": {description}" if description else ".")
                )

            print(
                f"Telegram accepted the video "
                f"({upload_path.stat().st_size / (1024 * 1024):.1f} MiB)."
            )
            return

    raise RuntimeError(
        f"{last_description} Compression and upload were attempted "
        f"{MAX_UPLOAD_ATTEMPTS} times."
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Send a rendered MP4 to Telegram, compressing it if needed."
    )
    parser.add_argument("--video", default="out/final.mp4")
    args = parser.parse_args()
    deliver_video(
        args.video,
        os.environ.get("BOT_TOKEN", ""),
        os.environ.get("CHAT_ID", ""),
    )


if __name__ == "__main__":
    main()
