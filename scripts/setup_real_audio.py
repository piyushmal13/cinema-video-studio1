from __future__ import annotations

import argparse
import os
import shutil
import subprocess


TRACKS = (
    "phonk_bed.mp3",
    "cinema_bed.mp3",
    "sfx_whoosh.mp3",
    "sfx_boom.mp3",
    "sfx_pop.mp3",
)


def _ffmpeg_executable() -> str:
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg:
        return ffmpeg
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError as error:
        raise RuntimeError(
            "FFmpeg is required. Install ffmpeg or imageio-ffmpeg."
        ) from error


def _run_track(ffmpeg: str, output_path: str, inputs: list[str], filters: str, duration: float) -> None:
    subprocess.run(
        [
            ffmpeg,
            "-y",
            *inputs,
            "-filter_complex",
            filters,
            "-map",
            "[mix]",
            "-t",
            str(duration),
            "-c:a",
            "libmp3lame",
            "-b:a",
            "64k",
            output_path,
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=90,
    )
    if not os.path.isfile(output_path) or os.path.getsize(output_path) == 0:
        raise RuntimeError(f"FFmpeg did not produce the audio track: {output_path}")


def generate_audio_assets(output_dir: str = "assets/audio", duration: float = 45) -> list[str]:
    if duration < 10 or duration > 60:
        raise ValueError("Audio vault bed duration must be between 10 and 60 seconds.")
    os.makedirs(output_dir, exist_ok=True)
    ffmpeg = _ffmpeg_executable()
    beds = {
        "phonk_bed.mp3": (
            [
                "-f", "lavfi", "-i",
                "aevalsrc=0.22*sin(2*PI*55*t)*(0.72+0.28*sin(2*PI*0.08*t))"
                "+0.08*sin(2*PI*110*t)+0.045*sin(2*PI*164.81*t)"
                "+0.03*sin(2*PI*220*t):s=44100:d=45",
                "-f", "lavfi", "-i",
                "aevalsrc=0.075*(sin(2*PI*880*t)+0.38*sin(2*PI*1320*t))"
                "*abs(cos(2*PI*2*t))*abs(cos(2*PI*2*t))"
                "*abs(cos(2*PI*2*t))*abs(cos(2*PI*2*t)):s=44100:d=45",
                "-f", "lavfi", "-i",
                "aevalsrc=0.028*sin(2*PI*7800*t)"
                "*abs(cos(2*PI*4*t))*abs(cos(2*PI*4*t))"
                "*abs(cos(2*PI*4*t))*abs(cos(2*PI*4*t)):s=44100:d=45",
                "-f", "lavfi", "-i",
                "anoisesrc=color=pink:sample_rate=44100:duration=45",
            ],
            "[0:a]lowpass=f=900,volume=0.72[low];"
            "[1:a]lowpass=f=2200,volume=0.55[bell];"
            "[2:a]highpass=f=5000,lowpass=f=11000,volume=0.35[hat];"
            "[3:a]lowpass=f=2400,volume=0.018[air];"
            "[low][bell][hat][air]amix=inputs=4:duration=first:normalize=0,"
            "afade=t=in:st=0:d=1.2,afade=t=out:st=41:d=4,alimiter=limit=0.88[mix]",
        ),
        "cinema_bed.mp3": (
            [
                "-f", "lavfi", "-i",
                "aevalsrc=0.17*sin(2*PI*55*t)*(0.72+0.28*sin(2*PI*0.07*t))"
                "+0.10*sin(2*PI*82.41*t)+0.07*sin(2*PI*110*t)"
                "+0.04*sin(2*PI*164.81*t)+0.025*sin(2*PI*220*t):s=44100:d=45",
                "-f", "lavfi", "-i",
                "anoisesrc=color=pink:sample_rate=44100:duration=45",
            ],
            "[0:a]lowpass=f=1400,volume=0.72[a];"
            "[1:a]lowpass=f=2800,volume=0.016[b];"
            "[a][b]amix=inputs=2:duration=first:normalize=0,"
            "aecho=0.7:0.78:80:0.18,"
            "afade=t=in:st=0:d=2.2,afade=t=out:st=41:d=4,alimiter=limit=0.88[mix]",
        ),
    }
    fade_duration = min(4.0, duration / 3)
    fade_start = max(0.0, duration - fade_duration)
    for name, (inputs, filters) in beds.items():
        inputs = [
            item.replace("duration=45", f"duration={duration}").replace(
                ":d=45", f":d={duration}"
            )
            for item in inputs
        ]
        filters = filters.replace(
            "st=41:d=4", f"st={fade_start}:d={fade_duration}"
        )
        _run_track(ffmpeg, os.path.join(output_dir, name), inputs, filters, duration)

    effects = {
        "sfx_whoosh.mp3": (
            "anoisesrc=color=pink:sample_rate=44100:duration=0.85",
            "highpass=f=180,lowpass=f=8500,volume=0.5,"
            "afade=t=in:st=0:d=0.08,afade=t=out:st=0.5:d=0.35,"
            "alimiter=limit=0.9[mix]",
            0.85,
        ),
        "sfx_boom.mp3": (
            "aevalsrc=0.32*sin(2*PI*48*t)*exp(-3.2*t)"
            "+0.09*sin(2*PI*96*t)*exp(-5*t):s=44100:d=1.5",
            "lowpass=f=260,aecho=0.65:0.55:65:0.24,"
            "afade=t=in:st=0:d=0.015,afade=t=out:st=0.72:d=0.78,"
            "alimiter=limit=0.9[mix]",
            1.5,
        ),
        "sfx_pop.mp3": (
            "aevalsrc=0.14*(sin(2*PI*660*t)+0.45*sin(2*PI*990*t))"
            "*exp(-8*t):s=44100:d=0.42",
            "lowpass=f=3200,afade=t=in:st=0:d=0.01,"
            "afade=t=out:st=0.18:d=0.24,alimiter=limit=0.88[mix]",
            0.42,
        ),
    }
    for name, (source, filters, effect_duration) in effects.items():
        _run_track(
            ffmpeg,
            os.path.join(output_dir, name),
            ["-f", "lavfi", "-i", source],
            filters,
            effect_duration,
        )

    total_bytes = sum(os.path.getsize(os.path.join(output_dir, name)) for name in TRACKS)
    if total_bytes >= 5 * 1024 * 1024:
        raise RuntimeError(f"Audio vault exceeds 5 MiB ({total_bytes} bytes).")
    return [os.path.join(output_dir, name) for name in TRACKS]


def ensure_audio_assets(output_dir: str = "assets/audio") -> list[str]:
    paths = [os.path.join(output_dir, name) for name in TRACKS]
    if all(os.path.isfile(path) and os.path.getsize(path) > 0 for path in paths):
        return paths
    return generate_audio_assets(output_dir)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate compact, keyless audio stems.")
    parser.add_argument("--output-dir", default="assets/audio")
    parser.add_argument("--duration", type=float, default=45)
    args = parser.parse_args()
    tracks = generate_audio_assets(args.output_dir, args.duration)
    total_bytes = sum(os.path.getsize(path) for path in tracks)
    print(f"Generated {len(tracks)} audio stems ({total_bytes} bytes) in {args.output_dir}.")


if __name__ == "__main__":
    main()
