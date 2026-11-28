import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import render_quality_gate


class RenderQualityGateCliTests(unittest.TestCase):
    def test_help_command_has_no_conflicting_arguments(self):
        result = subprocess.run(
            [sys.executable, "scripts/render_quality_gate.py", "--help"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.count("  --video-data VIDEO_DATA"), 1)
        self.assertIn("--minimum-media-ratio", result.stdout)

    def test_critical_storyboard_warning_is_not_overwritten_or_ignored(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            video = root / "video.mp4"
            video.write_bytes(b"test")
            data = root / "video_data.json"
            data.write_text(json.dumps({"scenes": [{"headline": "One"}]}), encoding="utf-8")
            report = root / "report.json"
            warnings = ["Scene media is missing: media/missing.jpg"]
            with patch("sys.argv", [
                "render_quality_gate.py", "--video", str(video),
                "--video-data", str(data), "--report", str(report),
            ]):
                with patch.object(render_quality_gate, "audit_render", return_value={"passed": True}):
                    with patch.object(render_quality_gate, "audit_visual_plan", return_value={
                        "passed": True, "warnings": warnings, "errors": [],
                    }):
                        code = render_quality_gate.main()
            result = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual(code, 1)
            self.assertFalse(result["plan"]["passed"])
            self.assertEqual(result["plan"]["critical_warnings"], warnings)
            self.assertFalse(result["passed"])


if __name__ == "__main__":
    unittest.main()
