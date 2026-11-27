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


    def test_variation_key_prevents_cross_production_asset_reuse(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            first = root / "first.jpg"
            second = root / "second.jpg"
            first.write_bytes(bytes([255, 216]) + b"a" * 6000)
            second.write_bytes(bytes([255, 216]) + b"b" * 6000)
            cache = MediaAssetCache(root / "cache")
            cache.store("gold bars in a vault", "vertical", first, "image", variation="job-1")
            cache.store("gold bars in a vault", "vertical", second, "image", variation="job-2")

            hit_one = cache.get(
                "gold bars in a vault", "vertical", expected_kind="image", variation="job-1"
            )
            hit_two = cache.get(
                "gold bars in a vault", "vertical", expected_kind="image", variation="job-2"
            )
            no_cross_hit = cache.get(
                "gold bars in a vault", "vertical", expected_kind="image", variation="job-3"
            )

        self.assertEqual(hit_one[0].read_bytes(), first.read_bytes())
        self.assertEqual(hit_two[0].read_bytes(), second.read_bytes())
        self.assertIsNone(no_cross_hit)

if __name__ == "__main__":
    unittest.main()
