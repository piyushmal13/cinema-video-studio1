import unittest
from unittest.mock import patch

from scripts.longform_director import documentary_direction, documentary_scene_count
from scripts.research_director import fetch_live_research, route_production_request


class ResearchDirectorTests(unittest.TestCase):
    def test_short_prompt_routes_to_vertical_reel_without_network_research(self):
        with patch("scripts.research_director.fetch_live_research") as research:
            route = route_production_request("Explain gold liquidity")

        self.assertEqual(route.format_hint, "vertical")
        self.assertEqual(route.duration_sec, 45)
        self.assertFalse(route.documentary)
        self.assertIn("--duration=45s", route.prompt)
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


    def test_daily_market_update_routes_to_vertical_and_fetches_quotes_and_news(self):
        from scripts.research_director import is_market_update_request

        self.assertTrue(is_market_update_request("Aaj pura gold market overview banao"))
        self.assertFalse(is_market_update_request("Explain how gold futures contracts work"))

        with (
            patch("scripts.research_director.fetch_market_research", return_value="timestamped quote + news") as research,
        ):
            route = route_production_request("Aaj pura market ka overview nikal kar reel banao")

        self.assertTrue(route.market_update)
        self.assertFalse(route.documentary)
        self.assertEqual(route.format_hint, "vertical")
        self.assertIn("--duration=50s", route.prompt)
        self.assertIn("timestamped quote", route.research_context)
        research.assert_called_once()

    def test_verbose_instruction_does_not_automatically_become_documentary(self):
        route = route_production_request(
            "Create a detailed vertical video explaining how solar panels work, "
            "include the physics, costs, home installation examples, common myths, "
            "and practical advice for beginners."
        )
        self.assertFalse(route.documentary)
        self.assertEqual(route.format_hint, "vertical")

    def test_generic_ifx_research_mode_fetches_public_research_leads(self):
        from unittest.mock import patch
        from scripts.research_director import route_production_request
        with patch.dict("os.environ", {"CINEMA_RESEARCH_ALL_IFX": "1"}):
            with patch("scripts.research_director.fetch_live_research", return_value="Research lead: example source"):
                route = route_production_request("Explain how gold spreads work", research_enabled=True)
        self.assertIn("Research lead", route.research_context)

    def test_generic_research_remains_off_when_profile_flag_is_absent(self):
        from unittest.mock import patch
        from scripts.research_director import route_production_request
        with patch.dict("os.environ", {}, clear=True):
            with patch("scripts.research_director.fetch_live_research") as research:
                route = route_production_request("Explain how gold spreads work", research_enabled=True)
        research.assert_not_called()
        self.assertEqual(route.research_context, "")


if __name__ == "__main__":
    unittest.main()
