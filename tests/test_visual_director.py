import unittest

from scripts.visual_director import (
    CAMERA_MOTIONS,
    VISUAL_TREATMENTS,
    assign_visual_language,
)


class VisualDirectorTests(unittest.TestCase):
    def test_scene_types_receive_semantically_appropriate_compositions(self):
        scenes = [
            {"type": "split_compare", "headline": "Two paths", "visualQuery": "two different workflows"},
            {"type": "step_list", "headline": "The sequence", "visualQuery": "hands assembling machine"},
            {"type": "process_diagram", "headline": "How it works", "visualQuery": "industrial process line"},
            {"type": "data_viz", "headline": "Measured change", "visualQuery": "research data display"},
            {"type": "cinema_outro", "headline": "The conclusion", "visualQuery": "city lights at dusk"},
        ]
        result = assign_visual_language(scenes, "explainer", "job-1", "vertical")
        self.assertEqual(result[0]["visualTreatment"], "comparative_split")
        self.assertEqual(result[1]["visualTreatment"], "vertical_timeline")
        self.assertEqual(result[2]["visualTreatment"], "process_blueprint")
        self.assertIn(result[3]["visualTreatment"], {"data_stage", "market_chart"})
        self.assertEqual(result[4]["visualTreatment"], "cinema_end_frame")

    def test_repeated_hero_scenes_do_not_receive_one_repeated_template(self):
        scenes = [
            {"type": "cinema_hero", "headline": f"Beat {index}", "visualQuery": f"subject detail {index}"}
            for index in range(10)
        ]
        result = assign_visual_language(scenes, "general", "unique-production-7")
        treatments = [item["visualTreatment"] for item in result]
        self.assertGreaterEqual(len(set(treatments)), 5)
        self.assertTrue(all(item in VISUAL_TREATMENTS for item in treatments))
        self.assertTrue(all(a != b for a, b in zip(treatments, treatments[1:])))

    def test_camera_grammar_and_transitions_change_across_adjacent_scenes(self):
        scenes = [
            {"type": "editorial_montage", "headline": f"Beat {index}", "visualQuery": f"visual idea {index}", "cameraMotion": "zoom_in"}
            for index in range(8)
        ]
        result = assign_visual_language(scenes, "technology", "motion-job")
        motions = [item["cameraMotion"] for item in result]
        transitions = [item["transitionStyle"] for item in result]
        self.assertTrue(all(item in CAMERA_MOTIONS for item in motions))
        self.assertTrue(all(a != b for a, b in zip(motions, motions[1:])))
        self.assertTrue(all(a != b for a, b in zip(transitions, transitions[1:])))

    def test_orientation_is_carried_to_every_scene(self):
        scenes = [{"type": "cinema_hero", "headline": "Wide image", "visualQuery": "city panorama"}]
        result = assign_visual_language(scenes, "travel", "wide-job", "landscape")
        self.assertEqual(result[0]["composition"], "widescreen")
        self.assertIn(result[0]["captionStyle"], {"ticker", "minimal", "documentary", "karaoke"})


if __name__ == "__main__":
    unittest.main()
