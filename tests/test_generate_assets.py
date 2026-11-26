import json
import unittest
from unittest.mock import Mock, patch

from scripts import generate_assets


class GenerateAssetsTests(unittest.TestCase):
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
            patch.object(generate_assets, "GEMINI_API_KEY", ""),
            patch.object(generate_assets, "GROQ_API_KEY", ""),
            patch.object(generate_assets.requests, "post", return_value=response) as post,
        ):
            result = generate_assets.generate_storyboard("A test prompt", "A test system prompt", 5)

        self.assertEqual(result, storyboard)
        self.assertEqual(post.call_args.kwargs["json"]["response_format"], {"type": "json_object"})
        self.assertEqual(post.call_args.kwargs["json"]["max_tokens"], 4096)

    def test_pollinations_free_limit_is_reported_without_retrying_other_models(self):
        response = Mock(
            status_code=402,
            text='{"error":{"code":"FREE_LIMIT","message":"Retry after 35s"}}',
        )

        with (
            patch.object(generate_assets, "GEMINI_API_KEY", ""),
            patch.object(generate_assets, "GROQ_API_KEY", ""),
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
            patch.object(generate_assets, "GROQ_API_KEY", ""),
            patch.object(generate_assets.requests, "post", side_effect=[short_response, valid_response]) as post,
            patch.object(generate_assets.time, "sleep") as sleep,
        ):
            result = generate_assets.generate_storyboard("A test prompt", "A test system prompt", 5)

        self.assertEqual(result, valid_storyboard)
        self.assertEqual(post.call_count, 2)
        self.assertIn("at least 5 words", post.call_args_list[1].kwargs["json"]["messages"][1]["content"])
        sleep.assert_called_once_with(46)


if __name__ == "__main__":
    unittest.main()
