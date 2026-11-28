import tempfile
import unittest
from pathlib import Path

from scripts.visual_quality import audit_visual_plan


class VisualQualityTests(unittest.TestCase):
    def test_detects_reused_media_across_scene_sequences(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            asset = root / "shared.jpg"
            asset.write_bytes(b"\xff\xd8\xff" + b"x" * 32)
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
                (root / name).write_bytes(b"\xff\xd8\xff" + name.encode() + b"x" * 32)
            scenes = [
                {"mediaKind": "image", "mediaFiles": ["a.jpg", "b.jpg"]},
                {"mediaKind": "none"},
            ]
            report = audit_visual_plan(scenes, root)
            self.assertEqual(report["media_backed_scenes"], 1)


    def test_reports_and_can_enforce_low_media_coverage(self):
        scenes = [
            {"mediaKind": "image", "mediaFile": "a.jpg"},
            {"mediaKind": "none", "mediaMode": "graphic"},
            {"mediaKind": "none", "mediaMode": "graphic"},
            {"mediaKind": "none", "mediaMode": "graphic"},
            {"mediaKind": "none", "mediaMode": "graphic"},
        ]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "a.jpg").write_bytes(b"\\xff\\xd8\\xff" + b"verified jpeg fixture")
            report = audit_visual_plan(scenes, root, minimum_media_ratio=0.60)
        self.assertEqual(report["media_backed_scenes"], 1)
        self.assertEqual(report["media_coverage_ratio"], 0.2)
        self.assertEqual(report["intentionally_graphic_scenes"], 4)
        self.assertTrue(any("Media coverage is 1/5 scenes" in item for item in report["warnings"]))

        enforced = audit_visual_plan(
            scenes, ".", minimum_media_ratio=0.60, enforce_media_ratio=True
        )
        self.assertFalse(enforced["passed"])
        self.assertTrue(any("required minimum is 60%" in item for item in enforced["errors"]))

    def test_media_coverage_counts_only_existing_nonempty_assets(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "valid.jpg").write_bytes(b"\xff\xd8\xff" + b"valid image bytes")
            (root / "empty.jpg").write_bytes(b"")
            scenes = [
                {"mediaKind": "image", "mediaFile": "valid.jpg"},
                {"mediaKind": "image", "mediaFile": "missing.jpg"},
                {"mediaKind": "image", "mediaFile": "empty.jpg"},
                {"mediaMode": "graphic", "type": "kinetic_type"},
            ]
            report = audit_visual_plan(scenes, root, minimum_media_ratio=0.25, enforce_media_ratio=True)
        self.assertEqual(report["media_backed_scenes"], 1)
        self.assertEqual(report["media_coverage_ratio"], 0.25)
        self.assertTrue(any("Scene media is missing" in warning for warning in report["warnings"]))

    def test_missing_media_fails_enforced_coverage(self):
        with tempfile.TemporaryDirectory() as directory:
            report = audit_visual_plan(
                [{"mediaKind": "image", "mediaFile": "missing.jpg"}],
                directory,
                minimum_media_ratio=0.60,
                enforce_media_ratio=True,
            )
        self.assertFalse(report["passed"])
        self.assertEqual(report["media_backed_scenes"], 0)
        self.assertTrue(any("Media coverage is 0/1" in error for error in report["errors"]))

    def test_rejects_non_image_payload_even_when_file_exists(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "fake.jpg").write_bytes(b"this is not a jpeg")
            report = audit_visual_plan(
                [{"mediaKind": "image", "mediaFile": "fake.jpg"}],
                root,
                minimum_media_ratio=0.60,
                enforce_media_ratio=True,
            )
        self.assertEqual(report["media_backed_scenes"], 0)
        self.assertFalse(report["passed"])

    def test_rejects_scene_media_path_traversal(self):
        report = audit_visual_plan(
            [{"mediaKind": "image", "mediaFile": "../outside.jpg"}], "."
        )
        self.assertFalse(report["passed"])
        self.assertTrue(any("escapes the public directory" in item for item in report["errors"]))


if __name__ == "__main__":
    unittest.main()
