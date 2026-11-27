from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any


HASHTAGS = {
    "market_update": ["#MarketUpdate", "#GoldMarket", "#ForexMarkets", "#MacroNews"],
    "commercial": ["#BrandFilm", "#ProductStory", "#CreativeCampaign"],
    "explainer": ["#LearnSomething", "#Explained", "#VisualLearning"],
    "technology": ["#Technology", "#Innovation", "#TechExplained"],
    "travel": ["#TravelFilm", "#Explore", "#TravelStories"],
    "story": ["#Documentary", "#Storytelling", "#ShortFilm"],
    "general": ["#VideoStory", "#CreativeStudio", "#WatchAndLearn"],
}


def _safe_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _hashtags(data: dict[str, Any]) -> list[str]:
    kind = _safe_text(data.get("topicKind")) or "general"
    tags = list(HASHTAGS.get(kind, HASHTAGS["general"]))
    if _safe_text(data.get("brandTag")).upper() == "IFXTRADES":
        tags.append("#IFXTrades")
    return tags[:6]


def build_social_package(data: dict[str, Any]) -> dict[str, Any]:
    title = _safe_text(data.get("title")) or "New video"
    narration = _safe_text(data.get("narration"))
    if not narration:
        narration = "Watch the complete video for the full explanation."
    description = narration[:1200]
    kind = _safe_text(data.get("topicKind")) or "general"
    format_name = "9:16 vertical" if data.get("format") == "vertical" else "16:9 widescreen"
    hashtags = _hashtags(data)

    notes = []
    if kind == "market_update":
        notes.append(
            "Market information is time-sensitive and may be delayed. "
            "This is general information, not a personalised trading recommendation."
        )
    if data.get("degradedMode"):
        notes.append(
            "This version used the studio's degraded fallback because the primary script provider was unavailable."
        )
    provider = _safe_text(data.get("storyboardProvider"))
    if provider:
        notes.append(f"Production engine: {provider}")

    caption_parts = [title, description]
    if notes and kind == "market_update":
        caption_parts.append(notes[0])
    caption_parts.append(" ".join(hashtags))
    caption = "\n\n".join(part for part in caption_parts if part)
    caption = caption[:1000]

    source_text = _safe_text(data.get("researchContext"))
    source_urls = list(dict.fromkeys(re.findall(r"https?://[^\s,)]+", source_text)))[:10]
    return {
        "title": title,
        "description": description,
        "caption": caption,
        "hashtags": hashtags,
        "platform": ["Instagram Reels", "YouTube Shorts", "TikTok"],
        "aspect_ratio": format_name,
        "topic_kind": kind,
        "brand": _safe_text(data.get("brandTag")),
        "input_mode": _safe_text(data.get("inputMode")),
        "storyboard_provider": provider,
        "degraded_mode": bool(data.get("degradedMode")),
        "notes": notes,
        "sources": source_urls,
    }


def create_cover(video_path: Path, output_path: Path, aspect: str) -> bool:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        try:
            import imageio_ffmpeg

            ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        except ImportError:
            return False
    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.run(
            [
                ffmpeg, "-y", "-ss", "0.5", "-i", str(video_path),
                "-frames:v", "1",
                "-vf",
                "scale=320:320:force_original_aspect_ratio=decrease,"
                "pad=320:320:(ow-iw)/2:(oh-ih)/2",
                "-q:v", "5", str(output_path),
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=45,
        )
    except (OSError, subprocess.SubprocessError) as error:
        print(f"Cover-frame extraction failed: {error}")
        return False
    if not output_path.is_file() or output_path.stat().st_size > 200_000:
        output_path.unlink(missing_ok=True)
        return False
    return True


def run(video_path: str | Path, data_path: str | Path, output_dir: str | Path) -> dict[str, Any]:
    video = Path(video_path)
    video_data_path = Path(data_path)
    output = Path(output_dir)
    if not video.is_file() or not video.stat().st_size:
        raise FileNotFoundError(f"Rendered MP4 is missing: {video}")
    data = json.loads(video_data_path.read_text(encoding="utf-8"))
    package = build_social_package(data)
    output.mkdir(parents=True, exist_ok=True)
    (output / "social_caption.md").write_text(
        f"# {package['title']}\n\n{package['description']}\n\n"
        + " ".join(package["hashtags"]) + "\n",
        encoding="utf-8",
    )
    (output / "telegram_caption.txt").write_text(package["caption"], encoding="utf-8")
    cover_path = output / "cover.jpg"
    if create_cover(video, cover_path, package["aspect_ratio"]):
        package["cover"] = str(cover_path)
        (output / "social_package.json").write_text(
            json.dumps(package, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    else:
        package["cover"] = None
    (output / "social_package.json").write_text(
        json.dumps(package, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(
        f"Prepared social package: {package['title']} | "
        f"{len(package['hashtags'])} tags | cover={'yes' if package['cover'] else 'no'}"
    )
    return package


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate platform post copy and a cover frame.")
    parser.add_argument("--video", default="out/final.mp4")
    parser.add_argument("--data", default="public/video_data.json")
    parser.add_argument("--output-dir", default="out")
    args = parser.parse_args()
    run(args.video, args.data, args.output_dir)


if __name__ == "__main__":
    main()
