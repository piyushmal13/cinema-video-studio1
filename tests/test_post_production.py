import unittest

from scripts.post_production import build_social_package


class PostProductionTests(unittest.TestCase):
    def test_market_package_has_topic_specific_copy_and_disclaimer(self):
        package = build_social_package({
            "title": "Gold Market: Session Overview",
            "narration": "Gold futures moved during the session as the dollar and yields changed.",
            "topicKind": "market_update",
            "format": "vertical",
            "brandTag": "",
            "inputMode": "brief",
            "researchContext": "Gold futures source https://finance.yahoo.com/quote/GC=F",
            "storyboardProvider": "pollinations:openai",
        })
        self.assertEqual(package["title"], "Gold Market: Session Overview")
        self.assertIn("Market information is time-sensitive", package["caption"])
        self.assertNotIn("#IFXTrades", package["caption"])
        self.assertIn("https://finance.yahoo.com/quote/GC=F", package["sources"])
        self.assertIn("#MarketUpdate", package["hashtags"])

    def test_ifx_branding_is_only_added_for_explicit_brand_profile(self):
        generic = build_social_package({
            "title": "A Technology Explainer",
            "narration": "A short technical explanation.",
            "topicKind": "technology",
            "format": "vertical",
            "brandTag": "",
        })
        branded = build_social_package({
            "title": "IFX Market Update",
            "narration": "A market update.",
            "topicKind": "market_update",
            "format": "vertical",
            "brandTag": "IFXTRADES",
        })
        self.assertNotIn("#IFXTrades", generic["caption"])
        self.assertIn("#IFXTrades", branded["caption"])

    def test_degraded_mode_is_disclosed_in_package_metadata(self):
        package = build_social_package({
            "title": "A Story",
            "narration": "The narration.",
            "topicKind": "general",
            "format": "vertical",
            "degradedMode": True,
        })
        self.assertTrue(package["degraded_mode"])
        self.assertTrue(any("degraded fallback" in note for note in package["notes"]))


if __name__ == "__main__":
    unittest.main()
