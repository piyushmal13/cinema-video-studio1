import unittest

from scripts.creative_director import (
    choose_video_scene_indexes,
    classify_topic,
    detect_language,
    detect_supplied_script,
    diversify_scenes,
    infer_creative_intent,
)


class CreativeDirectorTests(unittest.TestCase):
    def test_detects_roman_hindi_in_natural_telegram_prompt(self):
        brief = "Pane hisab se aaj pura market ka overview nikal kar ek accha updates reel banao"
        self.assertEqual(detect_language(brief), "Hinglish")
        intent = infer_creative_intent(brief)
        self.assertEqual(intent.topic_kind, "market_update")
        self.assertTrue(intent.research_required)
        self.assertEqual(intent.input_mode, "brief")

    def test_script_marker_preserves_user_supplied_narration(self):
        script = (
            "Gold moved higher during the session. The dollar softened after the release. "
            "Yields also moved lower. These developments do not guarantee the next move."
        )
        mode, extracted = detect_supplied_script("Make a 30 sec reel.\nSCRIPT:\n" + script)
        self.assertEqual(mode, "script")
        self.assertEqual(extracted, script)

    def test_long_detailed_instruction_is_not_assumed_to_be_a_script(self):
        brief = (
            "Please create a detailed explainer about how an electric vehicle battery works. "
            "Show the materials, cell structure, charging process, thermal management, "
            "safety controls, degradation and practical limitations. Make it accessible "
            "for people who are new to engineering and use clear visual examples."
        )
        self.assertEqual(detect_supplied_script(brief)[0], "brief")

    def test_classifies_market_update_separately_from_general_explainer(self):
        self.assertEqual(classify_topic("Aaj ka gold market overview"), "market_update")
        self.assertEqual(classify_topic("Explain how gold futures contracts work"), "explainer")
        self.assertEqual(classify_topic("Create a launch video for a new product"), "commercial")

    def test_video_generation_positions_are_spread_across_story(self):
        scenes = [{"weight": 1.0} for _ in range(12)]
        selected = choose_video_scene_indexes(scenes, max_clips=3)
        self.assertEqual(len(selected), 3)
        self.assertIn(0, selected)
        self.assertIn(11, selected)
        self.assertGreaterEqual(max(selected) - min(selected), 8)

    def test_duplicate_visual_queries_are_repaired(self):
        scenes = [
            {"visualQuery": "cinematic gold market terminal closeup"},
            {"visualQuery": "cinematic gold market terminal closeup"},
            {"visualQuery": "gold bullion macro detail"},
        ]
        diversified = diversify_scenes(scenes)
        queries = [scene["visualQuery"].casefold() for scene in diversified]
        self.assertEqual(len(queries), len(set(queries)))


if __name__ == "__main__":
    unittest.main()
