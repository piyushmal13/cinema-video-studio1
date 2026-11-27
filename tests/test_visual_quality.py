import tempfile
import unittest
from pathlib import Path

from scripts.visual_quality import audit_visual_plan


class VisualQualityTests(unittest.TestCase):
    def test_detects_reused_media_across_scene_sequences(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            asset = root / "shared.jpg"
            asset.write_bytes(b"same visual asset")
            scenes = [
                {"mediaKind": "image", "mediaFiles": ["shared.jpg"], "visualTreatment": "hero_full_bleed"},
                {"mediaKind": "image", "mediaFile": "shared.jpg", "visualTreatment": "editorial_split"},
            ]
            report = audit_visual_plan(scenes, root)
            self.assertTrue(any("Duplicate media files are reused" in item for item in report["warnings"]))
            self.assertEqual(report["media_backed_scenes"], 2)

    def test_counts_media_backed_scenes_not_number_of_frames(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ("a.jpg", "b.jpg"):
                (root / name).write_bytes(name.encode())
            scenes = [
                {"mediaKind": "image", "mediaFiles": ["a.jpg", "b.jpg"]},
                {"mediaKind": "none"},
            ]
            report = audit_visual_plan(scenes, root)
            self.assertEqual(report["media_backed_scenes"], 1)


if __name__ == "__main__":
    unittest.main()
