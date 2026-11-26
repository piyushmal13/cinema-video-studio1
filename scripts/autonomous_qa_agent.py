from __future__ import annotations

import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _run(name: str, command, *, cwd: Path = ROOT, env=None, timeout: int = 900) -> tuple[bool, str]:
    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            env=env,
            shell=isinstance(command, str),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return False, f"{name}: {error}"
    output = (result.stdout + result.stderr).strip()
    if result.returncode:
        return False, f"{name} exited {result.returncode}.\n{output[-5000:]}"
    return True, output[-1500:]


def _check_video_data(data_path: Path, public_dir: Path) -> list[Path]:
    with data_path.open(encoding="utf-8") as source:
        data = json.load(source)
    if not isinstance(data.get("scenes"), list) or len(data["scenes"]) < 3:
        raise ValueError("video_data.json must contain at least three scenes.")
    if not isinstance(data.get("words"), list) or not data["words"]:
        raise ValueError("video_data.json must contain word timings.")
    beats = data.get("beatTimestamps")
    if not isinstance(beats, list) or any(
        not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0
        for value in beats
    ):
        raise ValueError("video_data.json must contain valid beatTimestamps.")
    if beats != sorted(beats):
        raise ValueError("beatTimestamps must be in ascending order.")

    audio_names = [
        data.get("voiceoverFile"),
        data.get("ambientScoreFile"),
        data.get("masterAudioFile"),
        data.get("sfxBoomFile"),
        data.get("sfxWhooshFile"),
        data.get("sfxPopFile"),
    ]
    audio_paths = [public_dir / name for name in audio_names if name]
    for path in audio_paths:
        if not path.is_file() or path.stat().st_size == 0:
            raise ValueError(f"Generated audio is missing or empty: {path.name}")
    return audio_paths


def _verify_audio_decodes(audio_paths: list[Path]) -> None:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        import imageio_ffmpeg

        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    for path in audio_paths:
        subprocess.run(
            [ffmpeg, "-v", "error", "-i", str(path), "-f", "null", "-"],
            check=True,
            capture_output=True,
            text=True,
            timeout=45,
        )


def _verify_render_streams(video_path: Path) -> None:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            import imageio_ffmpeg

            ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        subprocess.run(
            [
                ffmpeg, "-v", "error", "-i", str(video_path),
                "-map", "0:v:0", "-map", "0:a:0", "-f", "null", "-",
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        return
    result = subprocess.run(
        [
            ffprobe, "-v", "error", "-show_entries", "stream=codec_type",
            "-of", "json", str(video_path),
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    stream_types = {
        stream.get("codec_type")
        for stream in json.loads(result.stdout).get("streams", [])
    }
    if not {"video", "audio"}.issubset(stream_types):
        raise RuntimeError(f"Verification render has incomplete streams: {stream_types}")


def _run_isolated_pipeline() -> tuple[bool, str]:
    with tempfile.TemporaryDirectory(prefix="cinema-qa-") as temp_name:
        temp_dir = Path(temp_name)
        audio_dir = temp_dir / "assets" / "audio"
        public_dir = temp_dir / "public"
        output_dir = temp_dir / "out"
        audio_dir.mkdir(parents=True)
        (public_dir / "media").mkdir(parents=True)
        output_dir.mkdir(parents=True)
        env = os.environ.copy()
        env.update(
            {
                "CINEMA_OFFLINE": "1",
                "CINEMA_AUDIO_ASSET_DIR": str(audio_dir),
                "FORMAT": "vertical",
                "PROMPT": "Explain how gold-market liquidity works",
            }
        )

        setup_ok, setup_log = _run(
            "Audio vault generation",
            [
                sys.executable, str(ROOT / "scripts" / "setup_real_audio.py"),
                "--output-dir", str(audio_dir),
            ],
            env=env,
            timeout=180,
        )
        if not setup_ok:
            return False, setup_log

        generate_ok, generate_log = _run(
            "Offline asset generation",
            [sys.executable, str(ROOT / "scripts" / "generate_assets.py")],
            cwd=temp_dir,
            env=env,
            timeout=240,
        )
        if not generate_ok:
            return False, generate_log

        try:
            audio_paths = _check_video_data(public_dir / "video_data.json", public_dir)
            _verify_audio_decodes(audio_paths)
            asset_paths = [audio_dir / filename for filename in (
                "phonk_bed.mp3", "cinema_bed.mp3", "sfx_whoosh.mp3",
                "sfx_boom.mp3", "sfx_pop.mp3",
            )]
            _verify_audio_decodes(asset_paths)
        except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
            return False, f"Generated schema/audio verification failed: {error}"

        rendered_path = output_dir / "qa_verify.mp4"
        render_command = (
            f'npx remotion render src/index.ts MainComp "{rendered_path}" '
            f'--frames=0-30 --gl=swangle '
            f'--props="{public_dir / "video_data.json"}" '
            f'--public-dir="{public_dir}"'
        )
        render_ok, render_log = _run(
            "31-frame Remotion render",
            render_command,
            env=env,
            timeout=600,
        )
        if not render_ok:
            return False, render_log
        try:
            if not rendered_path.is_file() or rendered_path.stat().st_size == 0:
                raise RuntimeError("Remotion did not produce the verification MP4.")
            _verify_render_streams(rendered_path)
        except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
            return False, f"Rendered MP4 verification failed: {error}"
        return True, (
            "Offline generator, audio decoding, video_data schema, and 31-frame "
            f"video/audio render passed.\n{generate_log}\n{render_log}"
        )


def main() -> int:
    results: list[tuple[str, bool, str]] = []
    for name, command in (
        ("Node tests", "npm test"),
        ("Python tests", "npm run test:python"),
        ("TypeScript", "npm exec tsc -- --noEmit"),
    ):
        ok, output = _run(name, command)
        results.append((name, ok, output))

    pipeline_ok, pipeline_log = _run_isolated_pipeline()
    results.append(("Isolated end-to-end render", pipeline_ok, pipeline_log))

    print("AUTONOMOUS QA REPORT")
    print("====================")
    for name, ok, output in results:
        print(f"[{'PASS' if ok else 'FAIL'}] {name}")
        if output:
            print(output)
    failures = [name for name, ok, _ in results if not ok]
    print(f"Result: {len(results) - len(failures)}/{len(results)} checks passed.")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
