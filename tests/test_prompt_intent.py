import unittest

from scripts.prompt_intent import (
    compose_story_prompt,
    parse_prompt_intent,
    validate_storyboard,
)


class PromptIntentTests(unittest.TestCase):
    def test_interprets_natural_format_duration_language_and_voice(self):
        intent = parse_prompt_intent(
            "/video Make a 90-second widescreen Hindi film with a female narrator",
            "vertical",
        )

        self.assertEqual(intent.format, "landscape")
        self.assertEqual(intent.mode, "cinema")
        self.assertEqual(intent.duration_sec, 90)
        self.assertEqual(intent.voice, "hi-IN-SwaraNeural")
        self.assertIn("90 seconds", intent.target_words)
        self.assertEqual(intent.min_narration_words, 194)
        self.assertNotIn("/video", intent.prompt)

    def test_preserves_prompt_topic_after_brand_option(self):
        intent = parse_prompt_intent(
            "/video --brand=IFXTRADES --color=#12abEF Explain how solar panels work"
        )

        self.assertEqual(intent.brand, "IFXTRADES")
        self.assertEqual(intent.color, "#12ABEF")
        self.assertEqual(intent.prompt, "Explain how solar panels work")

    def test_explicit_natural_format_overrides_workflow_hint(self):
        intent = parse_prompt_intent("Create a 30 sec vertical reel about ocean science", "landscape")

        self.assertEqual(intent.format, "vertical")
        self.assertEqual(intent.duration_sec, 30)

    def test_supports_hinglish_and_cli_duration(self):
        intent = parse_prompt_intent(
            "--movie --duration=2m --hinglish --female A story about India's moon mission"
        )

        self.assertEqual(intent.format, "landscape")
        self.assertEqual(intent.duration_sec, 120)
        self.assertEqual(intent.voice, "hi-IN-SwaraNeural")
        self.assertEqual(intent.prompt, "A story about India's moon mission")

    def test_rejects_bad_color_and_empty_prompt(self):
        with self.assertRaisesRegex(ValueError, "Color must use"):
            parse_prompt_intent("--color=gold Explain solar power")
        with self.assertRaisesRegex(ValueError, "non-empty"):
            parse_prompt_intent("   ")

    def test_context_is_explicit_and_latest_request_is_authoritative(self):
        self.assertEqual(compose_story_prompt("New topic"), "New topic")
        contextual = compose_story_prompt("Make it shorter", "A film about ocean science")

        self.assertIn("Earlier requests:", contextual)
        self.assertIn("Latest request:\nMake it shorter", contextual)
        self.assertIn("overrides conflicting earlier details", contextual)

    def test_storyboard_requires_complete_narration_and_valid_scenes(self):
        scenes = [
            {
                "type": "cinema_hero",
                "weight": 1,
                "kicker": "OPENING",
                "headline": f"Scene {index}",
                "visualQuery": "cinematic ocean waves at night",
                "cameraMotion": "zoom_in",
                "sfxCue": "whoosh",
            }
            for index in range(5)
        ]
        storyboard = {
            "narration": "A complete narration with enough words for the requested short film.",
            "scenes": scenes,
        }

        self.assertIs(validate_storyboard(storyboard, 10), storyboard)
        with self.assertRaisesRegex(ValueError, "too short"):
            validate_storyboard(
                {"narration": "Too short.", "scenes": scenes},
                10,
            )
        short_count = validate_storyboard(
            {"narration": "Enough narration words for this validation case.", "scenes": scenes[:4]},
            1,
        )
        self.assertEqual(len(short_count["scenes"]), 4)
        self.assertAlmostEqual(sum(scene["weight"] for scene in short_count["scenes"]), 1.0)

    def test_storyboard_scene_counts_are_padded_trimmed_and_weights_normalized(self):
        base_scene = {
            "type": "cinema_hero",
            "weight": 4,
            "kicker": "OPENING",
            "headline": "Scene",
            "visualQuery": "cinematic ocean waves at night",
            "cameraMotion": "zoom_in",
            "sfxCue": "whoosh",
        }
        narration = "Enough narration words for flexible scene count normalization."

        padded = validate_storyboard(
            {"narration": narration, "scenes": [dict(base_scene)]},
            1,
        )
        self.assertEqual(len(padded["scenes"]), 3)
        self.assertEqual([scene["weight"] for scene in padded["scenes"]], [0.25, 0.25, 0.5])

        many_scenes = [
            {**base_scene, "weight": index if index % 2 else 0}
            for index in range(1, 17)
        ]
        normalized = validate_storyboard(
            {"narration": narration, "scenes": many_scenes},
            1,
        )
        self.assertEqual(len(normalized["scenes"]), 14)
        self.assertAlmostEqual(sum(scene["weight"] for scene in normalized["scenes"]), 1.0)
        self.assertTrue(all(scene["weight"] > 0 for scene in normalized["scenes"]))

    def test_storyboard_rejects_bad_chart_data(self):
        scenes = [
            {
                "type": "three_d_bars",
                "weight": 1,
                "kicker": "CHART",
                "headline": "Scene",
                "visualQuery": "cinematic chart glowing in darkness",
                "cameraMotion": "zoom_in",
                "sfxCue": "pulse",
                "barValues": [{"label": "Q1", "value": -1}],
            }
            for _ in range(5)
        ]

        with self.assertRaisesRegex(ValueError, "invalid chart data"):
            validate_storyboard(
                {"narration": "Enough narration words for this chart validation.", "scenes": scenes},
                1,
            )


if __name__ == "__main__":
    unittest.main()
