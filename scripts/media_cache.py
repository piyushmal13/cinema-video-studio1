from __future__ import annotations

import hashlib
import os
import shutil
import time
import unicodedata
from pathlib import Path


_MEDIA_CACHE_VERSION = "v1"
_MAX_CACHE_BYTES = 512 * 1024 * 1024
_MAX_AGE_SECONDS = 30 * 24 * 60 * 60
_EXTENSIONS = {
    "video": (".mp4",),
    "image": (".jpg", ".jpeg", ".png", ".webp"),
}


class MediaAssetCache:
    def __init__(self, root: str | Path | None = None) -> None:
        self.root = Path(
            root
            or os.environ.get("CINEMA_MEDIA_CACHE_DIR", ".cache/cinema-media")
        )

    @staticmethod
    def _key(query: str, orientation: str) -> str:
        normalized_query = " ".join(
            unicodedata.normalize("NFKC", query).casefold().split()
        )
        identity = f"{_MEDIA_CACHE_VERSION}\0{orientation}\0{normalized_query}"
        return hashlib.sha256(identity.encode("utf-8")).hexdigest()

    @staticmethod
    def _asset_kind(path: Path) -> str | None:
        suffix = path.suffix.lower()
        try:
            with path.open("rb") as media_file:
                header = media_file.read(32)
        except OSError:
            return None

        if suffix == ".mp4" and b"ftyp" in header and path.stat().st_size > 50_000:
            return "video"
        if path.stat().st_size <= 5_000:
            return None
        if suffix in {".jpg", ".jpeg"} and header.startswith(b"\xff\xd8"):
            return "image"
        if suffix == ".png" and header.startswith(b"\x89PNG\r\n\x1a\n"):
            return "image"
        if suffix == ".webp" and header.startswith(b"RIFF") and b"WEBP" in header:
            return "image"
        return None

    def get(
        self,
        query: str,
        orientation: str,
        expected_kind: str | None = None,
    ) -> tuple[Path, str] | None:
        key = self._key(query, orientation)
        kinds = (expected_kind,) if expected_kind else ("video", "image")
        now = time.time()
        for kind in kinds:
            for extension in _EXTENSIONS[kind]:
                candidate = self.root / f"{key}{extension}"
                try:
                    age = now - candidate.stat().st_mtime
                except FileNotFoundError:
                    continue
                if age > _MAX_AGE_SECONDS or self._asset_kind(candidate) != kind:
                    candidate.unlink(missing_ok=True)
                    continue
                os.utime(candidate, None)
                return candidate, kind
        return None

    def store(
        self,
        query: str,
        orientation: str,
        source: str | Path,
        kind: str,
    ) -> Path | None:
        source_path = Path(source)
        if kind not in _EXTENSIONS or self._asset_kind(source_path) != kind:
            return None
        if source_path.stat().st_size > _MAX_CACHE_BYTES:
            return None
        extension = source_path.suffix.lower()
        if extension not in _EXTENSIONS[kind]:
            return None

        self.root.mkdir(parents=True, exist_ok=True)
        destination = self.root / f"{self._key(query, orientation)}{extension}"
        shutil.copyfile(source_path, destination)
        self._prune()
        return destination

    def _prune(self) -> None:
        now = time.time()
        entries = []
        total_bytes = 0
        for path in self.root.iterdir():
            if not path.is_file():
                continue
            try:
                stat = path.stat()
            except OSError:
                continue
            if now - stat.st_mtime > _MAX_AGE_SECONDS:
                path.unlink(missing_ok=True)
                continue
            total_bytes += stat.st_size
            entries.append((stat.st_mtime, path, stat.st_size))

        for _, path, size in sorted(entries):
            if total_bytes <= _MAX_CACHE_BYTES:
                break
            path.unlink(missing_ok=True)
            total_bytes -= size
