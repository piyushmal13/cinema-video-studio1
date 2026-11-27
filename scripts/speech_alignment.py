from __future__ import annotations

import os
from pathlib import Path
from typing import Any


def align_with_whisperx(
    audio_path: str | Path,
    narration: str,
    language: str = "en",
) -> list[dict[str, Any]] | None:
    """Return forced-aligned word timings when optional WhisperX is installed and enabled."""
    if os.environ.get("WHISPERX_ENABLED", "").casefold() not in {"1", "true", "yes"}:
        return None
    try:
        import torch
        import whisperx
    except ImportError as error:
        print(f"WhisperX alignment skipped; optional dependencies are not installed: {error}")
        return None

    path = Path(audio_path)
    if not path.is_file() or not narration.strip():
        return None

    device = "cuda" if torch.cuda.is_available() else "cpu"
    compute_type = os.environ.get("WHISPERX_COMPUTE_TYPE", "float16" if device == "cuda" else "int8")
    try:
        audio = whisperx.load_audio(str(path))
        model_a, metadata = whisperx.load_align_model(
            language_code=language, device=device
        )
        duration = float(len(audio)) / 16_000
        result = whisperx.align(
            [{"start": 0.0, "end": duration, "text": narration.strip()}],
            model_a,
            metadata,
            audio,
            device,
            return_char_alignments=False,
        )
        words: list[dict[str, Any]] = []
        for segment in result.get("segments", []):
            for word in segment.get("words", []):
                token = str(word.get("word", "")).strip()
                start, end = word.get("start"), word.get("end")
                if token and isinstance(start, (int, float)) and isinstance(end, (int, float)):
                    words.append({"word": token, "start": round(float(start), 3), "end": round(float(end), 3)})
        del model_a
        if words:
            print(f"WhisperX aligned {len(words)} words on {device} ({compute_type}).")
            return words
    except Exception as error:
        print(f"WhisperX alignment failed; retaining TTS timing fallback: {error}")
    return None
