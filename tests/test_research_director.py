import unittest
from unittest.mock import patch

from scripts.longform_director import documentary_direction, documentary_scene_count
from scripts.research_director import fetch_live_research, route_production_request


class ResearchDirectorTests(unittest.TestCase):
    def test_short_prompt_routes_to_vertical_reel_without_network_research(self):
        with patch("scripts.research_director.fetch_live_research") as research:
            route = route_production_request("Explain gold liquidity")

        self.assertEqual(route.format_hint, "vertical")
        self.assertEqual(route.duration_sec, 36)
        self.assertFalse(route.documentary)
        self.assertIn("--duration=36s", route.prompt)
        research.assert_not_called()

    def test_documentary_duration_and_live_research_are_routed(self):
        with patch(
            "scripts.research_director.fetch_live_research",
            return_value="Google News leads: gold-market context",
        ) as research:
            route = route_production_request("Make a documentary about gold, 3 min")

        self.assertEqual(route.format_hint, "landscape")
        self.assertEqual(route.duration_sec, 180)
        self.assertTrue(route.documentary)
        self.assertIn("--duration=180s", route.prompt)
        self.assertNotIn("--minutes", route.prompt)
        self.assertIn("Google News leads", route.research_context)
        research.assert_called_once()

    def test_minutes_flag_clamps_to_two_to_five_minutes(self):
        route = route_production_request(
            "--minutes=1 Explain how monetary policy changes the global economy",
            research_enabled=False,
        )
        self.assertEqual(route.format_hint, "landscape")
        self.assertEqual(route.duration_sec, 120)

        long_route = route_production_request(
            "A" * 200 + " --minutes=8",
            research_enabled=False,
        )
        self.assertEqual(long_route.duration_sec, 300)

    def test_longform_direction_uses_context_and_bounded_scene_count(self):
        self.assertEqual(documentary_scene_count(120), 8)
        self.assertEqual(documentary_scene_count(300), 14)
        direction = documentary_direction(180, "Search result lead")
        self.assertIn("180 seconds", direction)
        self.assertIn("untrusted context", direction)

    def test_live_research_treats_public_results_as_bounded_hints(self):
        news = type(
            "Response",
            (),
            {
                "content": b"<rss><channel><item><title>Gold market outlook</title></item></channel></rss>",
                "text": "<rss><channel><item><title>Gold market outlook</title></item></channel></rss>",
                "raise_for_status": lambda self: None,
            },
        )()
        search = type(
            "Response",
            (),
            {
                "json": lambda self: {
                    "AbstractText": "A concise background summary."
                },
                "raise_for_status": lambda self: None,
            },
        )()
        with patch(
            "scripts.research_director.requests.get",
            side_effect=[news, search],
        ) as get:
            context = fetch_live_research("Explain the gold market", timeout=3)

        self.assertIn("Gold market outlook", context)
        self.assertIn("DuckDuckGo context", context)
        self.assertEqual(get.call_count, 2)


if __name__ == "__main__":
    unittest.main()
