from __future__ import annotations

import argparse
import json
import os
from contextlib import ExitStack
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse

import requests


UPLOAD_TARGET_BYTES = 47 * 1024 * 1024
PUBLIC_HOST_LIMIT_BYTES = 100_000_000
PUBLIC_HOST_EXPIRY_SECONDS = 172_800
PUBLIC_HOST_UPLOAD_URL = "https://tmpfiles.org/api/v1/upload"


def _send_public_host_link(
    video_path: Path,
    bot_token: str,
    chat_id: str,
    post: Callable,
    caption: str = "",
) -> None:
    if video_path.stat().st_size > PUBLIC_HOST_LIMIT_BYTES:
        raise RuntimeError(
            "The video exceeds the temporary host's 100 MB file limit; "
            "render a smaller video to use this fallback."
        )

    try:
        with video_path.open("rb") as video_file:
            upload_response = post(
                PUBLIC_HOST_UPLOAD_URL,
                data={"expire": str(PUBLIC_HOST_EXPIRY_SECONDS)},
                files={"file": (video_path.name, video_file, "video/mp4")},
                timeout=(15, 600),
            )
    except requests.RequestException:
        raise RuntimeError(
            "The temporary video host could not be reached."
        ) from None

    if upload_response.status_code >= 400:
        raise RuntimeError(
            f"The temporary video host rejected the upload "
            f"(HTTP {upload_response.status_code})."
        )
    try:
        upload_result = upload_response.json()
    except ValueError:
        upload_result = {}
    upload_data = upload_result.get("data") if isinstance(upload_result, dict) else None
    link = upload_data.get("url") if isinstance(upload_data, dict) else None
    parsed_link = urlparse(link) if isinstance(link, str) else None
    if (
        not isinstance(upload_result, dict)
        or upload_result.get("status") != "success"
        or parsed_link is None
        or parsed_link.scheme != "https"
        or parsed_link.hostname != "tmpfiles.org"
    ):
        raise RuntimeError("The temporary video host returned an invalid upload link.")

    telegram_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    message = (
        (caption.strip() + "\n\n") if caption.strip() else ""
    ) + "Telegram could not accept this large video. Download it here within " + f"48 hours: {link}"
    try:
        message_response = post(
            telegram_url,
            data={"chat_id": chat_id, "text": message},
            timeout=(15, 30),
        )
    except requests.RequestException:
        raise RuntimeError(
            "The video was uploaded, but Telegram could not deliver its download link."
        ) from None

    if message_response.status_code >= 400:
        raise RuntimeError(
            "The video was uploaded, but Telegram rejected the download-link message "
            f"(HTTP {message_response.status_code})."
        )
    try:
        message_result = message_response.json()
    except ValueError:
        message_result = {}
    if not isinstance(message_result, dict) or message_result.get("ok") is not True:
        raise RuntimeError(
            "The video was uploaded, but Telegram did not confirm the download-link message."
        )
    print("Video exceeded Telegram's limit; sent a temporary download link (48-hour expiry).")


def deliver_video(
    video_path: str | Path,
    bot_token: str,
    chat_id: str,
    *,
    post: Callable = requests.post,
    caption: str = "Your finished cinema film is ready.",
    thumbnail_path: str | Path | None = None,
) -> None:
    source = Path(video_path)
    if not bot_token or not chat_id:
        raise ValueError("TELEGRAM_BOT_TOKEN and Telegram chat ID are required.")
    if not source.is_file() or source.stat().st_size == 0:
        raise FileNotFoundError(f"Rendered video is missing or empty: {source}")

    if source.stat().st_size > UPLOAD_TARGET_BYTES:
        _send_public_host_link(source, bot_token, chat_id, post, caption)
        return

    url = f"https://api.telegram.org/bot{bot_token}/sendVideo"
    files: dict[str, tuple] = {}
    with ExitStack() as stack:
        video_file = stack.enter_context(source.open("rb"))
        files["video"] = (source.name, video_file, "video/mp4")
        thumb = Path(thumbnail_path) if thumbnail_path else None
        if thumb and thumb.is_file() and 0 < thumb.stat().st_size <= 200_000:
            thumbnail_file = stack.enter_context(thumb.open("rb"))
            files["thumbnail"] = (thumb.name, thumbnail_file, "image/jpeg")
        response = post(
            url,
            data={
                "chat_id": chat_id,
                "caption": caption[:1024],
                "supports_streaming": "true",
            },
            files=files,
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
        _send_public_host_link(source, bot_token, chat_id, post, caption)
        return

    if response.status_code >= 400:
        description = result.get("description") if isinstance(result, dict) else None
        raise RuntimeError(
            f"Telegram sendVideo failed with HTTP {response.status_code}"
            + (f": {description}" if description else ".")
        )
    if not isinstance(result, dict) or result.get("ok") is not True:
        description = result.get("description") if isinstance(result, dict) else None
        raise RuntimeError(
            "Telegram did not confirm delivery"
            + (f": {description}" if description else ".")
        )

    print(f"Telegram accepted the video ({source.stat().st_size / (1024 * 1024):.1f} MiB).")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Send a rendered MP4 to Telegram or provide a temporary download link "
            "for large videos without transcoding."
        )
    )
    parser.add_argument("--video", default="out/final.mp4")
    parser.add_argument("--caption-file", default="")
    parser.add_argument("--thumbnail", default="out/cover.jpg")
    args = parser.parse_args()
    caption = "Your finished cinema film is ready."
    if args.caption_file:
        caption_path = Path(args.caption_file)
        if caption_path.is_file():
            caption = caption_path.read_text(encoding="utf-8").strip() or caption
    thumbnail = Path(args.thumbnail)
    deliver_video(
        args.video,
        os.environ.get("BOT_TOKEN", ""),
        os.environ.get("CHAT_ID", ""),
        caption=caption,
        thumbnail_path=thumbnail if thumbnail.is_file() else None,
    )


if __name__ == "__main__":
    main()
