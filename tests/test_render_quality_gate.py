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


if __name__ == "__main__":
    unittest.main()
