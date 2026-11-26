from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone

import requests


_VIRAL_FLAGS = re.compile(r"(?<!\S)--(?:phonk|viral|meme|trending)(?!\S)", re.IGNORECASE)
_ERROR_TREND = re.compile(r"^\d{3}$")


@dataclass(frozen=True)
class ViralPlan:
    archetype: str
    score_style: str
    beat_sync: bool
    fast_cuts: bool
    scene_count: int
    trending_context: str = ""

    @property
    def system_instruction(self) -> str:
        if self.archetype == "meme":
            return (
                "Use comedic or ironic contrast without inventing facts. Open with a "
                "pattern interrupt, build to a clear punchline, and keep each scene "
                "visually distinct. Make headlines short and high-contrast."
            )
        if self.archetype == "phonk":
            return (
                "Use an immediate pattern-interrupt hook, crisp short headlines, "
                "high-contrast visual beats, and fast but coherent pacing. Each scene "
                "must advance the explanation rather than repeat the same claim."
            )
        return (
            "Use measured documentary pacing, factual transitions, and a complete "
            "beginning, explanation, concrete example, and satisfying conclusion."
        )


def strip_viral_flags(prompt: str) -> str:
    cleaned = _VIRAL_FLAGS.sub("", prompt)
    return re.sub(r"\s+", " ", cleaned).strip()


def _trending_titles(xml_text: str, limit: int = 5) -> list[str]:
    if len(xml_text) > 256_000 or re.search(r"<!\s*(?:DOCTYPE|ENTITY)", xml_text, re.I):
        return []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []

    titles: list[str] = []
    for node in root.findall(".//item/title"):
        title = re.sub(r"\s+", " ", "".join(node.itertext())).strip()
        if (
            title
            and len(title) <= 120
            and not _ERROR_TREND.fullmatch(title)
            and re.search(r"[A-Za-z\u0900-\u097f]", title)
            and title.casefold() not in {item.casefold() for item in titles}
        ):
            titles.append(title)
        if len(titles) >= limit:
            break
    return titles


def fetch_trending_context(timeout: float = 6.0) -> str:
    response = requests.get(
        "https://trends.google.com/trending/rss?geo=IN",
        headers={"User-Agent": "CinemaVideoStudio/1.0"},
        timeout=timeout,
    )
    response.raise_for_status()
    titles = _trending_titles(response.text)
    if not titles:
        return ""
    fetched_at = datetime.now(timezone.utc).isoformat(timespec="minutes")
    topics = "; ".join(titles)
    return (
        f"Live Google Trends RSS topics for India, fetched {fetched_at}: {topics}. "
        "Use a trend only if it naturally fits the user's brief. Treat these titles "
        "as unverified topic hints, not evidence; do not infer facts or statistics."
    )


def build_viral_plan(
    prompt: str,
    mode: str,
    duration_sec: int,
    *,
    trending_context: str = "",
) -> ViralPlan:
    lower = prompt.casefold()
    if "--meme" in lower:
        archetype = "meme"
    elif mode == "cinema" or "--movie" in lower or "--cinema" in lower:
        archetype = "cinema"
    else:
        archetype = "phonk"

    fast_cuts = archetype in {"phonk", "meme"}
    scene_count = (
        max(5, min(24, round(duration_sec / 3)))
        if fast_cuts
        else 6
    )
    return ViralPlan(
        archetype=archetype,
        score_style="phonk" if fast_cuts else "cinema",
        beat_sync=fast_cuts,
        fast_cuts=fast_cuts,
        scene_count=scene_count,
        trending_context=trending_context,
    )


def enhance_story_prompt(prompt: str, plan: ViralPlan) -> str:
    parts = [prompt.strip(), plan.system_instruction]
    if plan.fast_cuts:
        parts.append(
            f"Create exactly {plan.scene_count} scenes for approximately 3-second "
            "cuts. Give every scene a distinct "
            "purpose, headline, and visual query. Keep the narration complete."
        )
    if plan.trending_context:
        parts.append(plan.trending_context)
    return "\n\n".join(part for part in parts if part)
