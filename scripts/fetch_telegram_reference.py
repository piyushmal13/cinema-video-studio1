#!/usr/bin/env python3
"""Fetch one user-supplied Telegram reference file for a private GitHub Actions job."""
from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from urllib.parse import urlparse

import requests

MAX_BYTES = 20 * 1024 * 1024
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".mp4", ".mov"}
ALLOWED_MIME = {
    "image/jpeg", "image/png", "image/webp", "video/mp4", "video/quicktime",
}


def fetch_reference(file_id: str, kind: str, mime_type: str, output_dir: str | Path, token: str) -> dict:
    if not re.fullmatch(r"[A-Za-z0-9_-]{8,512}={0,2}", file_id):
        raise ValueError("Telegram file_id has an unexpected format.")
    if kind not in {"image", "video"} or mime_type.lower() not in ALLOWED_MIME:
        raise ValueError("Only JPG, PNG, WEBP and MP4/MOV references are accepted.")
    headers = {"User-Agent": "Cinema-Reference-Fetch/1.0"}
    api = requests.get(
        f"https://api.telegram.org/bot{token}/getFile",
        params={"file_id": file_id}, headers=headers, timeout=(10, 30),
    )
    api.raise_for_status()
    payload = api.json()
    if not payload.get("ok") or not isinstance(payload.get("result"), dict):
        raise RuntimeError("Telegram did not return a file descriptor.")
    descriptor = payload["result"]
    remote_path = str(descriptor.get("file_path") or "")
    if not remote_path or ".." in Path(remote_path).parts:
        raise ValueError("Telegram returned an invalid file path.")
    declared_size = int(descriptor.get("file_size") or 0)
    if declared_size > MAX_BYTES:
        raise ValueError("Reference file exceeds the 20 MB Bot API download limit.")
    extension = Path(remote_path).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise ValueError("Telegram file extension is not in the supported image/video allowlist.")
    if (kind == "image" and extension not in {".jpg", ".jpeg", ".png", ".webp"}) or (
        kind == "video" and extension not in {".mp4", ".mov"}
    ):
        raise ValueError("Attachment kind and Telegram file extension do not match.")

    # The tokenized file URL is used only in memory; never print it or persist it.
    download = requests.get(
        f"https://api.telegram.org/file/bot{token}/{remote_path}",
        headers=headers, stream=True, timeout=(10, 90),
    )
    download.raise_for_status()
    target_dir = Path(output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"reference{extension}"
    temporary = target.with_suffix(target.suffix + ".part")
    received = 0
    try:
        with temporary.open("wb") as handle:
            for chunk in download.iter_content(chunk_size=1024 * 256):
                if not chunk:
                    continue
                received += len(chunk)
                if received > MAX_BYTES:
                    raise ValueError("Downloaded reference exceeded the 20 MB safety limit.")
                handle.write(chunk)
        if received == 0 or (declared_size and received != declared_size):
            raise RuntimeError("Downloaded reference size did not match Telegram metadata.")
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)
        download.close()

    manifest = {
        "schema_version": 1, "kind": kind, "mime_type": mime_type.lower(),
        "path": str(target), "size_bytes": received,
        "source": "telegram-user-upload", "rights": "user-supplied; verify permission before commercial use",
    }
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file-id", required=True)
    parser.add_argument("--kind", required=True, choices=["image", "video"])
    parser.add_argument("--mime-type", required=True)
    parser.add_argument("--output-dir", default="out/reference_media")
    parser.add_argument("--manifest", default="out/reference_manifest.json")
    args = parser.parse_args()
    token = os.environ.get("BOT_TOKEN", "").strip()
    if not token:
        parser.error("BOT_TOKEN environment variable is required")
    manifest = fetch_reference(args.file_id, args.kind, args.mime_type, args.output_dir, token)
    target = Path(args.manifest)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Fetched private Telegram reference: {manifest['kind']} ({manifest['size_bytes']} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
