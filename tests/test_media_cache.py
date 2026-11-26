from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.media_cache import MediaAssetCache


class MediaAssetCacheTests(unittest.TestCase):
    def test_reuses_valid_media_for_normalized_query(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source.jpg"
            source.write_bytes(b"\xff\xd8" + b"x" * 6000)
            cache = MediaAssetCache(root / "cache")

            stored = cache.store("Gold bars  in a vault", "vertical", source, "image")
            hit = cache.get(" gold BARS in a vault ", "vertical", expected_kind="image")
            other_orientation = cache.get(
                "gold bars in a vault",
                "landscape",
                expected_kind="image",
            )

        self.assertIsNotNone(stored)
        self.assertIsNotNone(hit)
        self.assertIsNone(other_orientation)
        self.assertEqual(hit[1], "image")
        self.assertEqual(hit[0].suffix, ".jpg")

    def test_cache_separates_orientation_and_rejects_bad_media(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source.jpg"
            source.write_bytes(b"not an image" + b"x" * 6000)
            cache = MediaAssetCache(root / "cache")

            stored = cache.store("gold", "vertical", source, "image")
            landscape_hit = cache.get("gold", "landscape")
            vertical_hit = cache.get("gold", "vertical")

        self.assertIsNone(stored)
        self.assertIsNone(landscape_hit)
        self.assertIsNone(vertical_hit)


if __name__ == "__main__":
    unittest.main()
