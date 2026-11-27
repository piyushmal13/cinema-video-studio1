from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any


def _language_profile(language: str) -> tuple[str, str]:
    if language.casefold().startswith("hi"):
        return (
            os.environ.get("KOKORO_HI_VOICE", "hf_alpha").strip() or "hf_alpha",
            "hi",
        )
    return (
        os.environ.get("KOKORO_EN_VOICE", "af_heart").strip() or "af_heart",
        "en-us",
    )


def _estimated_timings(text: str, duration: float) -> list[dict[str, Any]]:
    tokens = re.findall(r"\S+", text)
    if not tokens or duration <= 0:
        return []
    weights = [max(1, len(token.strip(".,!?;:()[]{}\"'"))) for token in tokens]
    total_weight = float(sum(weights))
    cursor = 0.0
    words: list[dict[str, Any]] = []
    for index, (token, weight) in enumerate(zip(tokens, weights)):
        start = cursor
        cursor = duration if index == len(tokens) - 1 else cursor + duration * weight / total_weight
        words.append({
            "word": token,
            "start": round(start, 3),
            "end": round(cursor, 3),
        })
    return words


def generate_from_environment(
    text: str,
    output_path: str | Path,
    language: str = "en",
) -> tuple[list[dict[str, Any]], float] | None:
    """Optional local Kokoro ONNX synthesis; returns None when not configured."""
    if os.environ.get("KOKORO_TTS_ENABLED", "").casefold() not in {"1", "true", "yes"}:
        return None

    model_path = Path(os.environ.get("KOKORO_MODEL_PATH", "models/kokoro-v1.0.onnx"))
    voices_path = Path(os.environ.get("KOKORO_VOICES_PATH", "models/voices-v1.0.bin"))
    if not model_path.is_file() or not voices_path.is_file():
        print(
            "Kokoro TTS is enabled but its ONNX model/voice files are missing; "
            "continuing with Edge TTS and gTTS."
        )
        return None

    try:
        from kokoro_onnx import Kokoro
        import soundfile as sf
    except ImportError as error:
        print(f"Kokoro TTS packages are not installed; continuing with standard TTS: {error}")
        return None

    voice, lang = _language_profile(language)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        try:
            import imageio_ffmpeg

            ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        except ImportError:
            print("Kokoro TTS needs FFmpeg to convert WAV to MP3; continuing with standard TTS.")
            return None

    temporary_wav = output.with_suffix(".kokoro.tmp.wav")
    temporary_mp3 = output.with_suffix(".kokoro.tmp.mp3")
    engine = None
    try:
        engine = Kokoro(str(model_path), str(voices_path))
        audio, sample_rate = engine.create(
            text,
            voice=voice,
            speed=float(os.environ.get("KOKORO_SPEED", "1.0")),
            lang=lang,
        )
        if audio is None or sample_rate <= 0 or len(audio) == 0:
            raise RuntimeError("Kokoro returned an empty audio array.")
        sf.write(str(temporary_wav), audio, sample_rate, subtype="PCM_16")
        subprocess.run(
            [
                ffmpeg, "-y", "-i", str(temporary_wav),
                "-codec:a", "libmp3lame", "-b:a", "128k",
                str(temporary_mp3),
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if not temporary_mp3.is_file() or temporary_mp3.stat().st_size < 1_000:
            raise RuntimeError("Kokoro MP3 conversion returned an empty file.")
        os.replace(temporary_mp3, output)
        duration = len(audio) / float(sample_rate)
        timings = _estimated_timings(text, duration)
        if not timings:
            raise RuntimeError("Kokoro audio could not be mapped to narration words.")
        print(f"Generated local Kokoro ONNX voiceover ({voice}, {lang}).")
        return timings, duration
    except Exception as error:
        print(f"Kokoro local TTS failed; continuing with Edge TTS and gTTS: {error}")
        return None
    finally:
        for path in (temporary_wav, temporary_mp3):
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass
        if engine is not None:
            try:
                engine.voices.close()
            except Exception:
                pass
