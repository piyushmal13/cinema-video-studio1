from __future__ import annotations

import tempfile
import unittest
import shutil
import subprocess
from pathlib import Path
from unittest.mock import Mock, patch

from scripts.deliver_video import (
    UPLOAD_TARGET_BYTES,
    _encode_under_limit,
    deliver_video,
)
from scripts.generate_assets import _ffmpeg_executable


class TelegramDeliveryTests(unittest.TestCase):
    def test_sends_small_video_without_transcoding(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            video = Path(temp_dir) / "final.mp4"
            video.write_bytes(b"small video")
            response = Mock(status_code=200, json=lambda: {"ok": True})
            post = Mock(return_value=response)

            deliver_video(video, "test-token", "123", post=post)

        post.assert_called_once()
        self.assertEqual(post.call_args.args[0], "https://api.telegram.org/bottest-token/sendVideo")
        self.assertEqual(post.call_args.kwargs["data"]["chat_id"], "123")

    def test_compresses_video_above_safe_upload_target(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            video = Path(temp_dir) / "final.mp4"
            video.write_bytes(b"x" * (UPLOAD_TARGET_BYTES + 1))
            compressed = Path(temp_dir) / "telegram-ready.mp4"
            compressed.write_bytes(b"compressed")
            response = Mock(status_code=200, json=lambda: {"ok": True})
            post = Mock(return_value=response)

            with patch(
                "scripts.deliver_video._encode_under_limit",
                return_value=compressed,
            ) as encode:
                deliver_video(
                    video,
                    "test-token",
                    "123",
                    ffmpeg="ffmpeg",
                    ffprobe="ffprobe",
                    post=post,
                )

        encode.assert_called_once()
        self.assertEqual(post.call_args.kwargs["files"]["video"][0], "telegram-ready.mp4")

    def test_413_recompresses_once_without_repeating_same_payload(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            video = Path(temp_dir) / "final.mp4"
            video.write_bytes(b"small but rejected")
            compressed = Path(temp_dir) / "telegram-ready.mp4"
            compressed.write_bytes(b"compressed")
            post = Mock(
                side_effect=[
                    Mock(status_code=413, json=lambda: {
                        "ok": False,
                        "description": "Request Entity Too Large",
                    }),
                    Mock(status_code=200, json=lambda: {"ok": True}),
                ]
            )

            with patch(
                "scripts.deliver_video._encode_under_limit",
                return_value=compressed,
            ) as encode:
                deliver_video(
                    video,
                    "test-token",
                    "123",
                    ffmpeg="ffmpeg",
                    ffprobe="ffprobe",
                    post=post,
                )

        self.assertEqual(post.call_count, 2)
        self.assertEqual(encode.call_count, 1)
        self.assertLess(
            encode.call_args.args[2],
            UPLOAD_TARGET_BYTES,
        )

    def test_compressed_mp4_is_valid_and_below_target(self):
        ffmpeg = _ffmpeg_executable()
        ffprobe = shutil.which("ffprobe")
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "source.mp4"
            destination = Path(temp_dir) / "telegram-ready.mp4"
            subprocess.run(
                [
                    ffmpeg, "-y",
                    "-f", "lavfi", "-i", "testsrc2=size=720x1280:rate=24",
                    "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=44100",
                    "-t", "6",
                    "-c:v", "libx264", "-preset", "ultrafast", "-b:v", "5000k",
                    "-c:a", "aac", "-b:a", "128k",
                    str(source),
                ],
                check=True,
                capture_output=True,
            )
            result = _encode_under_limit(
                source,
                destination,
                3 * 1024 * 1024,
                ffmpeg,
                ffprobe,
            )
            subprocess.run(
                [ffmpeg, "-v", "error", "-i", str(result), "-f", "null", "-"],
                check=True,
                capture_output=True,
            )
            self.assertLessEqual(result.stat().st_size, 3 * 1024 * 1024)

    def test_repeated_413_fails_explicitly_after_bounded_attempts(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            video = Path(temp_dir) / "final.mp4"
            video.write_bytes(b"small but rejected")
            compressed = Path(temp_dir) / "telegram-ready.mp4"
            compressed.write_bytes(b"compressed")
            too_large = lambda: Mock(
                status_code=413,
                json=lambda: {"ok": False, "description": "Request Entity Too Large"},
            )
            post = Mock(side_effect=[too_large(), too_large(), too_large()])

            with (
                patch(
                    "scripts.deliver_video._encode_under_limit",
                    return_value=compressed,
                ),
                self.assertRaisesRegex(RuntimeError, "attempted 3 times"),
            ):
                deliver_video(
                    video,
                    "test-token",
                    "123",
                    ffmpeg="ffmpeg",
                    ffprobe="ffprobe",
                    post=post,
                )

        self.assertEqual(post.call_count, 3)

    def test_reports_telegram_api_rejection(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            video = Path(temp_dir) / "final.mp4"
            video.write_bytes(b"small video")
            response = Mock(
                status_code=400,
                json=lambda: {"ok": False, "description": "Chat not found"},
            )

            with self.assertRaisesRegex(RuntimeError, "Chat not found"):
                deliver_video(
                    video,
                    "test-token",
                    "123",
                    post=Mock(return_value=response),
                )


if __name__ == "__main__":
    unittest.main()
