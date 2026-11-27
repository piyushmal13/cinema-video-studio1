import json, tempfile, unittest
from datetime import datetime, timezone
from pathlib import Path
from scripts.repo_scout import score_repository
from scripts.hardware_doctor import inspect_hardware
from scripts.cost_ledger import build_record, append_record

class FreeProductionIntelligenceTests(unittest.TestCase):
    def test_repo_scout_rewards_permissive_license_and_recent_activity(self):
        now = datetime(2026, 11, 27, tzinfo=timezone.utc)
        item = {"full_name":"example/active-tool","license":{"spdx_id":"MIT"},
            "stargazers_count":1500,"pushed_at":"2026-11-20T00:00:00Z","archived":False,"fork":False}
        score, reasons = score_repository(item, now=now)
        self.assertGreaterEqual(score, 70)
        self.assertIn("permissive-license:mit", reasons)
        self.assertIn("active-within-30d", reasons)

    def test_repo_scout_flags_unknown_license_and_archived_project(self):
        score, reasons = score_repository({"full_name":"example/old-tool","license":None,
            "stargazers_count":0,"pushed_at":"2020-01-01T00:00:00Z","archived":True},
            now=datetime(2026,11,27,tzinfo=timezone.utc))
        self.assertEqual(score, 0)
        self.assertIn("archived", reasons)
        self.assertIn("license-needs-manual-review", reasons)

    def test_hardware_doctor_returns_safe_profile(self):
        report = inspect_hardware()
        self.assertIn(report["profile"], {"cpu-editorial","gpu-worker","amd-experimental"})
        self.assertIn("video_diffusion", report["model_policy"])

    def test_ledger_records_metrics_without_fake_cash_cost(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); video=root/"final.mp4"; video.write_bytes(b"mp4")
            data=root/"video_data.json"; data.write_text(json.dumps({"scenes":[{"mediaFile":"x.jpg"}],
                "voiceProvider":"edge-tts","storyboardProvider":"ollama"}),encoding="utf-8")
            record=build_record(job_id="t1",started_at=10,finished_at=16,output=video,video_data=data)
            self.assertEqual(record["duration_seconds"],6)
            self.assertEqual(record["video_bytes"],3)
            self.assertIsNone(record["accounting"]["cash_cost_usd"])
            ledger=root/"ledger.jsonl"; append_record(record,ledger)
            self.assertEqual(len(ledger.read_text().splitlines()),1)

if __name__ == "__main__": unittest.main()
