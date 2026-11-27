import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import kokoro_tts


class KokoroTtsTests(unittest.TestCase):
    def test_disabled_provider_does_not_load_optional_dependencies(self):
        with patch.dict("os.environ", {"KOKORO_TTS_ENABLED": "0"}, clear=False):
            self.assertIsNone(kokoro_tts.generate_from_environment("Hello", "voice.mp3", "en"))

    def test_generates_local_hindi_voiceover_with_word_timings(self):
        instances = []

        class FakeVoices:
            def __init__(self):
                self.closed = False

            def close(self):
                self.closed = True

        class FakeKokoro:
            def __init__(self, model_path, voices_path):
                self.model_path = model_path
                self.voices_path = voices_path
                self.voices = FakeVoices()
                self.calls = []
                instances.append(self)

            def create(self, text, **kwargs):
                self.calls.append((text, kwargs))
                return [0.1] * 16_000, 16_000

        def write_wav(path, audio, sample_rate, subtype):
            Path(path).write_bytes(b"wav data")

        fake_soundfile = types.SimpleNamespace(write=write_wav)
        fake_kokoro = types.SimpleNamespace(Kokoro=FakeKokoro)

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            model = root / "kokoro.onnx"
            voices = root / "voices.bin"
            model.write_bytes(b"model")
            voices.write_bytes(b"voices")
            output = root / "voiceover.mp3"

            def fake_ffmpeg(command, **kwargs):
                Path(command[-1]).write_bytes(b"x" * 2000)
                return types.SimpleNamespace(returncode=0)

            with (
                patch.dict(sys.modules, {
                    "kokoro_onnx": fake_kokoro,
                    "soundfile": fake_soundfile,
                }),
                patch.dict("os.environ", {
                    "KOKORO_TTS_ENABLED": "1",
                    "KOKORO_MODEL_PATH": str(model),
                    "KOKORO_VOICES_PATH": str(voices),
                    "KOKORO_HI_VOICE": "hf_alpha",
                }),
                patch.object(kokoro_tts.subprocess, "run", side_effect=fake_ffmpeg),
            ):
                result = kokoro_tts.generate_from_environment(
                    "Namaste duniya, yeh local voice test hai.",
                    output,
                    language="hi",
                )

            self.assertTrue(output.is_file())
            self.assertEqual(instances[0].calls[0][1]["voice"], "hf_alpha")
            self.assertEqual(instances[0].calls[0][1]["lang"], "hi")
            self.assertTrue(instances[0].voices.closed)

        words, duration = result
        self.assertGreaterEqual(len(words), 5)
        self.assertAlmostEqual(duration, 1.0, places=3)
        self.assertEqual(words[0]["start"], 0.0)
        self.assertAlmostEqual(words[-1]["end"], 1.0, places=3)

    def test_selects_english_voice_for_english_input(self):
        self.assertEqual(kokoro_tts._language_profile("en"), ("af_heart", "en-us"))
        self.assertEqual(kokoro_tts._language_profile("hi-IN"), ("hf_alpha", "hi"))


if __name__ == "__main__":
    unittest.main()
