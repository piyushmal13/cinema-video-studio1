import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.post_production import build_social_package, run


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

    def test_run_blocks_delivery_when_render_has_no_audio_video_or_valid_duration(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            video = root / "final.mp4"
            video.write_bytes(b"not really a video")
            data_path = root / "video_data.json"
            data_path.write_text(json.dumps({
                "title": "Test",
                "narration": "Test narration.",
                "topicKind": "general",
                "format": "vertical",
            }), encoding="utf-8")
            with patch(
                "scripts.post_production.audit_render",
                return_value={"passed": False, "errors": ["Expected video and audio streams"]},
            ):
                with self.assertRaisesRegex(RuntimeError, "Expected video and audio streams"):
                    run(video, data_path, root / "out")
            self.assertFalse((root / "out" / "telegram_caption.txt").exists())

    def test_run_records_render_quality_before_creating_social_outputs(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            video = root / "final.mp4"
            video.write_bytes(b"mock mp4 bytes")
            data_path = root / "video_data.json"
            data_path.write_text(json.dumps({
                "title": "A verified render",
                "narration": "A properly rendered explanation.",
                "topicKind": "explainer",
                "format": "vertical",
            }), encoding="utf-8")
            quality = {
                "passed": True,
                "duration_sec": 42.0,
                "streams": ["audio", "video"],
                "errors": [],
            }
            with (
                patch("scripts.post_production.audit_render", return_value=quality),
                patch("scripts.post_production.create_cover", return_value=False),
            ):
                package = run(video, data_path, root / "out")
            self.assertEqual(package["render_quality"], quality)
            saved = json.loads((root / "out" / "social_package.json").read_text(encoding="utf-8"))
            self.assertEqual(saved["render_quality"]["duration_sec"], 42.0)

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
