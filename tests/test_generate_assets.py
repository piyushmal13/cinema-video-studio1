import json
import os
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch

from scripts import generate_assets


class GenerateAssetsTests(unittest.TestCase):
    def test_ffmpeg_synthesizes_decodable_phonk_and_cinema_scores(self):
        ffmpeg = generate_assets._ffmpeg_executable()
        with tempfile.TemporaryDirectory() as temp_dir:
            for style in ("phonk", "cinema"):
                path = os.path.join(temp_dir, f"{style}.mp3")
                generate_assets.synthesize_ambient_cinema_score(8, path, [], style)
                self.assertGreater(os.path.getsize(path), 1000)
                subprocess.run(
                    [ffmpeg, "-v", "error", "-i", path, "-f", "null", "-"],
                    check=True,
                    capture_output=True,
                )

    def test_ffmpeg_synthesizes_decodable_transition_sfx(self):
        ffmpeg = generate_assets._ffmpeg_executable()
        with tempfile.TemporaryDirectory() as temp_dir:
            boom, whoosh = generate_assets.synthesize_transition_sfx(temp_dir)
            for filename in (boom, whoosh):
                path = os.path.join(temp_dir, filename)
                self.assertGreater(os.path.getsize(path), 1000)
                subprocess.run(
                    [ffmpeg, "-v", "error", "-i", path, "-f", "null", "-"],
                    check=True,
                    capture_output=True,
                )

    def test_pollinations_requests_json_mode(self):
        scenes = [
            {
                "type": "cinema_hero",
                "weight": 0.2,
                "kicker": "OPENING",
                "headline": f"Scene {index}",
                "visualQuery": "cinematic ocean waves at night",
                "cameraMotion": "zoom_in",
                "sfxCue": "whoosh",
            }
            for index in range(5)
        ]
        storyboard = {
            "narration": "A complete narration with enough words for this test case.",
            "scenes": scenes,
        }
        response = Mock(
            status_code=200,
            json=lambda: {
                "choices": [{"message": {"content": json.dumps(storyboard)}}]
            },
        )

        with (
            patch.object(generate_assets, "GEMINI_API_KEY", "test-gemini-key"),
            patch.object(generate_assets.requests, "post", return_value=response) as post,
        ):
            result = generate_assets.generate_storyboard("A test prompt", "A test system prompt", 5)

        self.assertEqual(result, storyboard)
        self.assertEqual(post.call_args.args[0], "https://text.pollinations.ai/openai")
        self.assertEqual(post.call_args.kwargs["json"]["response_format"], {"type": "json_object"})
        self.assertEqual(post.call_args.kwargs["json"]["max_tokens"], 8192)

    def test_video_generation_uses_pollinations_for_high_impact_scenes(self):
        response = Mock(
            status_code=200,
            content=b"\x00\x00\x00\x20ftyp" + b"x" * 60_000,
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = os.path.join(temp_dir, "scene.mp4")
            with (
                patch.object(generate_assets.requests, "get", return_value=response) as get,
                patch.object(generate_assets, "_is_valid_mp4", return_value=True),
            ):
                generated = generate_assets.try_generate_ai_video_clip(
                    "A dramatic gold-market visual", 0, "vertical", output_path
                )

            self.assertTrue(generated)
            self.assertTrue(os.path.isfile(output_path))
            self.assertIn("model=wan", get.call_args.args[0])
            self.assertIn("width=480&height=832", get.call_args.args[0])

    def test_video_generation_skips_non_hero_scenes(self):
        with patch.object(generate_assets.requests, "get") as get:
            self.assertFalse(
                generate_assets.try_generate_ai_video_clip(
                    "A visual", 1, "landscape", "unused.mp4"
                )
            )
        get.assert_not_called()

    def test_video_generation_uses_zero_gpu_after_pollinations_fails(self):
        response = Mock(status_code=429, content=b"")
        child_result = Mock(returncode=1, stderr="Space unavailable", stdout="")
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = os.path.join(temp_dir, "scene.mp4")
            with (
                patch.object(generate_assets.requests, "get", return_value=response),
                patch.object(generate_assets.subprocess, "run", return_value=child_result) as run,
            ):
                generated = generate_assets.try_generate_ai_video_clip(
                    "A dramatic gold-market visual", 2, "landscape", output_path
                )

        self.assertFalse(generated)
        self.assertFalse(os.path.exists(output_path))
        self.assertEqual(run.call_args.kwargs["timeout"] <= 45, True)
        self.assertIn("Lightricks/ltx-video-distilled", run.call_args.args[0])

    def test_zero_gpu_output_is_rejected_if_not_a_valid_mp4(self):
        response = Mock(status_code=429, content=b"")
        child_result = Mock(returncode=0, stderr="", stdout="")
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = os.path.join(temp_dir, "scene.mp4")

            def create_invalid_output(*args, **kwargs):
                with open(output_path, "wb") as file:
                    file.write(b"not an mp4")
                return child_result

            with (
                patch.object(generate_assets.requests, "get", return_value=response),
                patch.object(generate_assets.subprocess, "run", side_effect=create_invalid_output),
                patch.object(generate_assets, "_is_valid_mp4", return_value=False),
            ):
                generated = generate_assets.try_generate_ai_video_clip(
                    "A dramatic gold-market visual", 0, "vertical", output_path
                )

        self.assertFalse(generated)
        self.assertFalse(os.path.exists(output_path))

    def test_wikimedia_uses_only_public_domain_or_cc0_jpegs(self):
        flux = Mock(status_code=503, content=b"")
        commons = Mock(
            json=lambda: {
                "query": {
                    "pages": {
                        "1": {
                            "title": "File:Gold image.jpg",
                            "imageinfo": [{
                                "thumburl": "https://commons.example/gold.jpg",
                                "extmetadata": {
                                    "LicenseShortName": {"value": "CC0"}
                                },
                            }],
                        }
                    }
                }
            }
        )
        commons.raise_for_status = Mock()
        photo = Mock(
            content=b"\xff\xd8" + b"x" * 6000,
            headers={"Content-Type": "image/jpeg"},
        )
        photo.raise_for_status = Mock()
        original_dir = os.getcwd()
        with tempfile.TemporaryDirectory() as temp_dir:
            os.chdir(temp_dir)
            try:
                os.makedirs("public/media")
                with patch.object(
                    generate_assets.requests,
                    "get",
                    side_effect=[flux, commons, photo],
                ):
                    result = generate_assets.fetch_broll_or_ai_visual(
                        "gold bars in a vault", 1, "vertical"
                    )
                self.assertEqual(result, ("media/scene_1_photo.jpg", "image"))
                self.assertTrue(os.path.isfile("public/media/scene_1_photo.jpg"))
            finally:
                os.chdir(original_dir)

    def test_pollinations_free_limit_is_reported_without_retrying_other_models(self):
        response = Mock(
            status_code=402,
            text='{"error":{"code":"FREE_LIMIT","message":"Retry after 35s"}}',
        )

        with (
            patch.object(generate_assets, "GEMINI_API_KEY", ""),
            patch.object(generate_assets.requests, "post", side_effect=[response, response]) as post,
            patch.object(generate_assets.time, "sleep") as sleep,
        ):
            with self.assertRaisesRegex(RuntimeError, "HTTP 402.*FREE_LIMIT"):
                generate_assets.generate_storyboard("A test prompt", "A test system prompt", 5)

        self.assertEqual(post.call_count, 2)
        sleep.assert_called_once_with(36)

    def test_short_storyboard_is_retried_with_an_explicit_minimum(self):
        scenes = [
            {
                "type": "cinema_hero",
                "weight": 0.2,
                "kicker": "OPENING",
                "headline": f"Scene {index}",
                "visualQuery": "cinematic ocean waves at night",
                "cameraMotion": "zoom_in",
                "sfxCue": "whoosh",
            }
            for index in range(5)
        ]
        short_response = Mock(
            status_code=200,
            json=lambda: {
                "choices": [{
                    "message": {
                        "content": json.dumps({"narration": "Too short.", "scenes": scenes})
                    }
                }]
            },
        )
        valid_storyboard = {
            "narration": "A complete narration with enough words for this test case.",
            "scenes": scenes,
        }
        valid_response = Mock(
            status_code=200,
            json=lambda: {
                "choices": [{
                    "message": {"content": json.dumps(valid_storyboard)}
                }]
            },
        )

        with (
            patch.object(generate_assets, "GEMINI_API_KEY", ""),
            patch.object(generate_assets.requests, "post", side_effect=[short_response, valid_response]) as post,
            patch.object(generate_assets.time, "sleep") as sleep,
        ):
            result = generate_assets.generate_storyboard("A test prompt", "A test system prompt", 5)

        self.assertEqual(result, valid_storyboard)
        self.assertEqual(post.call_count, 2)
        self.assertIn("at least 5 words", post.call_args_list[1].kwargs["json"]["messages"][1]["content"])
        sleep.assert_called_once_with(46)

    def test_gemini_is_only_used_as_an_optional_fallback(self):
        scenes = [
            {
                "type": "cinema_hero",
                "weight": 0.2,
                "kicker": "OPENING",
                "headline": f"Scene {index}",
                "visualQuery": "cinematic ocean waves at night",
                "cameraMotion": "zoom_in",
                "sfxCue": "whoosh",
            }
            for index in range(5)
        ]
        storyboard = {
            "narration": "A complete narration with enough words for this test case.",
            "scenes": scenes,
        }
        limited = Mock(
            status_code=402,
            text='{"error":{"code":"FREE_LIMIT","message":"Retry after 35s"}}',
        )
        gemini = Mock(
            status_code=200,
            json=lambda: {
                "candidates": [{
                    "content": {"parts": [{"text": json.dumps(storyboard)}]}
                }]
            },
        )

        with (
            patch.object(generate_assets, "GEMINI_API_KEY", "test-gemini-key"),
            patch.object(generate_assets.requests, "post", side_effect=[limited, limited, gemini]) as post,
            patch.object(generate_assets.time, "sleep"),
        ):
            result = generate_assets.generate_storyboard("A test prompt", "A test system prompt", 5)

        self.assertEqual(result, storyboard)
        self.assertEqual(
            [call.args[0] for call in post.call_args_list],
            [
                "https://text.pollinations.ai/openai",
                "https://text.pollinations.ai/openai",
                "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.8-flash:generateContent?key=test-gemini-key",
            ],
        )


if __name__ == "__main__":
    unittest.main()
