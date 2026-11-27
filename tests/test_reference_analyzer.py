import json
import tempfile
import unittest
from pathlib import Path

from scripts.reference_analyzer import (
    build_style_brief,
    probe_video,
    smart_crop_image,
    prepare_reference_images,
)


class ReferenceAnalyzerTests(unittest.TestCase):
    def test_video_probe_is_graceful_without_media_or_ffprobe(self):
        result = probe_video("does-not-exist.mp4")
        self.assertFalse(result["available"])

    def test_style_brief_records_reference_limits_and_orientation(self):
        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory) / "reference.png"
            try:
                from PIL import Image
            except ImportError:
                self.skipTest("Pillow optional dependency is not installed")
            Image.new("RGB", (800, 1200), (30, 40, 50)).save(image)
            report = build_style_brief(None, [str(image)], directory)
            self.assertEqual(report["schema_version"], 1)
            self.assertEqual(report["reference_images"][0]["orientation"], "portrait")
            self.assertTrue(report["limitations"])

    def test_smart_crop_respects_target_dimensions(self):
        with tempfile.TemporaryDirectory() as directory:
            try:
                from PIL import Image
            except ImportError:
                self.skipTest("Pillow optional dependency is not installed")
            source = Path(directory) / "source.png"
            output = Path(directory) / "fitted.jpg"
            Image.new("RGB", (1200, 800), (120, 80, 40)).save(source)
            result = smart_crop_image(source, output, 360, 640, focal_x=0.7, focal_y=0.5)
            self.assertTrue(result["ok"])
            with Image.open(output) as fitted:
                self.assertEqual(fitted.size, (360, 640))
            self.assertEqual(result["focal_point"], [0.7, 0.5])


    def test_user_reference_image_is_assigned_to_a_scene_and_fitted(self):
        with tempfile.TemporaryDirectory() as directory:
            try:
                from PIL import Image
            except ImportError:
                self.skipTest("Pillow optional dependency is not installed")
            root = Path(directory)
            source = root / "reference.png"
            Image.new("RGB", (800, 1200), (30, 40, 50)).save(source)
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps({"kind": "image", "path": str(source)}), encoding="utf-8")
            scenes = [
                {"headline": "Opening scene", "visualQuery": "city skyline"},
                {"headline": "Product detail", "visualQuery": "closeup product packaging"},
            ]
            assigned = prepare_reference_images(scenes, manifest, "vertical", root / "public")
            self.assertEqual(assigned, {0: "media/user_reference_01.jpg"})
            self.assertTrue((root / "public" / "media" / "user_reference_01.jpg").is_file())


if __name__ == "__main__":
    unittest.main()
