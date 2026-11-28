from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from scripts.deliver_video import (
    PUBLIC_HOST_LIMIT_BYTES,
    UPLOAD_TARGET_BYTES,
    deliver_video,
)


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

    def test_oversized_video_is_linked_without_transcoding(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            video = Path(temp_dir) / "final.mp4"
            video.write_bytes(b"x" * (UPLOAD_TARGET_BYTES + 1))
            post = Mock(
                side_effect=[
                    Mock(
                        status_code=200,
                        json=lambda: {
                            "status": "success",
                            "data": {"url": "https://tmpfiles.org/123/final.mp4"},
                        },
                    ),
                    Mock(status_code=200, json=lambda: {"ok": True}),
                ]
            )
            deliver_video(video, "test-token", "123", post=post)

        self.assertEqual(post.call_count, 2)
        self.assertEqual(
            post.call_args_list[0].args[0],
            "https://tmpfiles.org/api/v1/upload",
        )
        self.assertEqual(post.call_args_list[0].kwargs["files"]["file"][0], "final.mp4")
        self.assertEqual(
            post.call_args.args[0],
            "https://api.telegram.org/bottest-token/sendMessage",
        )

    def test_telegram_413_sends_original_direct_link_without_retrying(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            video = Path(temp_dir) / "final.mp4"
            video.write_bytes(b"small but rejected")
            post = Mock(
                side_effect=[
                    Mock(
                        status_code=413,
                        json=lambda: {
                            "ok": False,
                            "description": "Request Entity Too Large",
                        },
                    ),
                    Mock(
                        status_code=200,
                        json=lambda: {
                            "status": "success",
                            "data": {"url": "https://tmpfiles.org/123/final.mp4"},
                        },
                    ),
                    Mock(status_code=200, json=lambda: {"ok": True}),
                ]
            )
            deliver_video(video, "test-token", "123", post=post)

        self.assertEqual(post.call_count, 3)
        self.assertEqual(post.call_args_list[0].args[0], "https://api.telegram.org/bottest-token/sendVideo")
        self.assertEqual(post.call_args_list[1].args[0], "https://tmpfiles.org/api/v1/upload")
        self.assertEqual(
            post.call_args.args[0],
            "https://api.telegram.org/bottest-token/sendMessage",
        )
        self.assertIn("within 48 hours", post.call_args.kwargs["data"]["text"])

    def test_public_link_uses_original_file_and_expiry(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            video = Path(temp_dir) / "final.mp4"
            video.write_bytes(b"x" * (UPLOAD_TARGET_BYTES + 1))
            post = Mock(
                side_effect=[
                    Mock(
                        status_code=200,
                        json=lambda: {
                            "status": "success",
                            "data": {"url": "https://tmpfiles.org/123/final.mp4"},
                        },
                    ),
                    Mock(status_code=200, json=lambda: {"ok": True}),
                ]
            )
            deliver_video(video, "test-token", "123", post=post)

        upload_call = post.call_args_list[0]
        self.assertEqual(upload_call.args[0], "https://tmpfiles.org/api/v1/upload")
        self.assertEqual(upload_call.kwargs["data"]["expire"], "172800")

    def test_public_host_rejects_files_over_its_documented_limit(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            video = Path(temp_dir) / "too-large.mp4"
            with video.open("wb") as file:
                file.truncate(PUBLIC_HOST_LIMIT_BYTES + 1)

            with self.assertRaisesRegex(RuntimeError, "100 MB file limit"):
                deliver_video(
                    video,
                    "test-token",
                    "123",
                    post=Mock(),
                )

    def test_uses_custom_caption_and_thumbnail_for_telegram_delivery(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            video = Path(temp_dir) / "final.mp4"
            video.write_bytes(b"small video")
            thumbnail = Path(temp_dir) / "cover.jpg"
            thumbnail.write_bytes(bytes([255, 216]) + b"x" * 6000)
            response = Mock(status_code=200, json=lambda: {"ok": True})
            post = Mock(return_value=response)

            deliver_video(
                video,
                "test-token",
                "123",
                post=post,
                caption="A subject-specific update #MarketUpdate",
                thumbnail_path=thumbnail,
            )

        self.assertEqual(post.call_args.kwargs["data"]["caption"], "A subject-specific update #MarketUpdate")
        self.assertIn("thumbnail", post.call_args.kwargs["files"])

    def test_413_fallback_keeps_generated_caption_in_download_message(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            video = Path(temp_dir) / "final.mp4"
            video.write_bytes(b"small but rejected")
            post = Mock(side_effect=[
                Mock(status_code=413, json=lambda: {"ok": False, "description": "Request Entity Too Large"}),
                Mock(status_code=200, json=lambda: {"status": "success", "data": {"url": "https://tmpfiles.org/123/final.mp4"}}),
                Mock(status_code=200, json=lambda: {"ok": True}),
            ])
            deliver_video(video, "test-token", "123", post=post, caption="A subject-specific market update")
        message = post.call_args.kwargs["data"]["text"]
        self.assertIn("A subject-specific market update", message)
        self.assertIn("within 48 hours", message)

    def test_uses_durable_release_url_for_large_video(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            video = Path(temp_dir) / "final.mp4"
            video.write_bytes(b"x" * (UPLOAD_TARGET_BYTES + 1))
            post = Mock(return_value=Mock(status_code=200, json=lambda: {"ok": True}))
            deliver_video(
                video, "test-token", "123", post=post,
                download_url="https://github.com/piyushmal13/cinema-video-studio1/releases/download/cinema-run-1/final.mp4",
            )
        self.assertEqual(post.call_count, 1)
        self.assertEqual(post.call_args.args[0], "https://api.telegram.org/bottest-token/sendMessage")
        self.assertIn("no temporary expiry", post.call_args.kwargs["data"]["text"])
        self.assertIn("releases/download/cinema-run-1/final.mp4", post.call_args.kwargs["data"]["text"])

    def test_rejects_non_release_durable_download_url(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            video = Path(temp_dir) / "final.mp4"
            video.write_bytes(b"x" * (UPLOAD_TARGET_BYTES + 1))
            with self.assertRaisesRegex(ValueError, "GitHub Releases"):
                deliver_video(video, "test-token", "123", post=Mock(), download_url="https://example.com/video.mp4")

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


    def test_network_failure_falls_back_to_temporary_link(self):
        import requests
        with tempfile.TemporaryDirectory() as temp_dir:
            video = Path(temp_dir) / "final.mp4"
            video.write_bytes(b"video after interrupted Telegram upload")
            post = Mock(side_effect=[
                requests.ConnectionError("Telegram connection interrupted"),
                Mock(status_code=200, json=lambda: {
                    "status": "success",
                    "data": {"url": "https://tmpfiles.org/123/final.mp4"},
                }),
                Mock(status_code=200, json=lambda: {"ok": True}),
            ])
            deliver_video(video, "test-token", "123", post=post)
        self.assertEqual(post.call_count, 3)
        self.assertEqual(post.call_args_list[1].args[0], "https://tmpfiles.org/api/v1/upload")
        self.assertEqual(post.call_args.args[0], "https://api.telegram.org/bottest-token/sendMessage")


if __name__ == "__main__":
    unittest.main()
