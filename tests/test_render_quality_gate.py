import unittest

from scripts.render_quality_gate import overlapping_boxes


class RenderQualityGateTests(unittest.TestCase):
    def test_detects_intersecting_text_boxes(self):
        rows = [
            {"level": "5", "text": "ENTRY", "left": "10", "top": "10", "width": "100", "height": "30"},
            {"level": "5", "text": "TRADER", "left": "40", "top": "18", "width": "100", "height": "30"},
        ]
        self.assertEqual(len(overlapping_boxes(rows)), 1)

    def test_does_not_flag_separate_text_lines(self):
        rows = [
            {"level": "5", "text": "TITLE", "left": "10", "top": "10", "width": "100", "height": "25"},
            {"level": "5", "text": "SUBTITLE", "left": "10", "top": "50", "width": "140", "height": "20"},
        ]
        self.assertEqual(overlapping_boxes(rows), [])

    def test_ignores_non_word_tesseract_rows(self):
        rows = [{"level": "4", "text": "LINE", "left": "10", "top": "10", "width": "100", "height": "20"}]
        self.assertEqual(overlapping_boxes(rows), [])


    def test_ignores_punctuation_only_ocr_tokens(self):
        rows = [
            {"level": "5", "text": "CHART", "left": "10", "top": "10", "width": "100", "height": "30"},
            {"level": "5", "text": "’", "left": "20", "top": "15", "width": "20", "height": "15"},
        ]
        self.assertEqual(overlapping_boxes(rows), [])

    def test_ignores_single_glyph_duplicate_inside_recognized_word(self):
        # Reproduces run 46122577779: Tesseract emitted an isolated "e"
        # whose center was inside the correctly recognized "Analysis" box.
        rows = [
            {"level": "5", "text": "e", "left": "408", "top": "80", "width": "9", "height": "8"},
            {"level": "5", "text": "Analysis", "left": "295", "top": "83", "width": "140", "height": "31"},
        ]
        self.assertEqual(overlapping_boxes(rows), [])

    def test_still_detects_real_single_character_collision_outside_a_word(self):
        rows = [
            {"level": "5", "text": "A", "left": "10", "top": "10", "width": "30", "height": "30"},
            {"level": "5", "text": "TITLE", "left": "30", "top": "15", "width": "100", "height": "30"},
        ]
        self.assertEqual(len(overlapping_boxes(rows)), 1)

    def test_quality_gate_cli_help_has_no_duplicate_video_data_option(self):
        import subprocess
        import sys
        result = subprocess.run(
            [sys.executable, "scripts/render_quality_gate.py", "--help"],
            capture_output=True, text=True, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--video-data", result.stdout)


if __name__ == "__main__":
    unittest.main()
