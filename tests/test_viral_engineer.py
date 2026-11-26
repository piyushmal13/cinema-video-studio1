import unittest
from unittest.mock import Mock, patch

from scripts.viral_engineer import (
    _trending_titles,
    build_viral_plan,
    enhance_story_prompt,
    fetch_trending_context,
    strip_viral_flags,
)


class ViralEngineerTests(unittest.TestCase):
    def test_short_form_defaults_to_phonk_and_targets_three_second_cuts(self):
        plan = build_viral_plan("Explain compound interest", "shorts", 45)

        self.assertEqual(plan.archetype, "phonk")
        self.assertEqual(plan.score_style, "phonk")
        self.assertTrue(plan.beat_sync)
        self.assertTrue(plan.fast_cuts)
        self.assertEqual(plan.scene_count, 15)

    def test_meme_and_cinema_select_distinct_audio_and_pacing(self):
        meme = build_viral_plan("--meme Explain a market lesson", "shorts", 30)
        cinema = build_viral_plan("--cinema A history documentary", "cinema", 90)

        self.assertEqual(meme.archetype, "meme")
        self.assertEqual(meme.score_style, "phonk")
        self.assertEqual(meme.scene_count, 10)
        self.assertEqual(cinema.archetype, "cinema")
        self.assertEqual(cinema.score_style, "cinema")
        self.assertFalse(cinema.beat_sync)
        self.assertEqual(cinema.scene_count, 6)

    def test_flags_are_removed_without_losing_the_prompt(self):
        self.assertEqual(
            strip_viral_flags("--viral --trending Explain gold --meme"),
            "Explain gold",
        )

    def test_trending_parser_skips_error_titles_and_limits_results(self):
        feed = (
            "<rss><channel>"
            "<item><title>502</title></item>"
            "<item><title>Gold prices</title></item>"
            "<item><title>Gold prices</title></item>"
            "<item><title>Monsoon update</title></item>"
            "</channel></rss>"
        )

        self.assertEqual(_trending_titles(feed, limit=2), ["Gold prices", "Monsoon update"])
        self.assertEqual(_trending_titles("<!DOCTYPE x [<!ENTITY x 'boom'>]><rss/>"), [])

    def test_trending_fetch_is_bounded_and_adds_only_context(self):
        response = Mock(
            text="<rss><channel><item><title>India market news</title></item></channel></rss>"
        )
        response.raise_for_status = Mock()

        with patch("scripts.viral_engineer.requests.get", return_value=response) as get:
            context = fetch_trending_context(timeout=4.5)

        self.assertIn("India market news", context)
        self.assertIn("not evidence", context)
        self.assertEqual(get.call_args.kwargs["timeout"], 4.5)

    def test_enhanced_prompt_keeps_topic_and_cut_instructions(self):
        plan = build_viral_plan("Explain gold", "shorts", 30)

        prompt = enhance_story_prompt("Explain gold", plan)

        self.assertIn("Explain gold", prompt)
        self.assertIn("exactly 10 scenes", prompt)
        self.assertIn("pattern-interrupt hook", prompt)


if __name__ == "__main__":
    unittest.main()
