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
        if self.archetype == "newsroom":
            return (
                "Direct this as a modern newsroom explainer. Lead with the verified "
                "development, show why it matters, compare relevant evidence, explain "
                "uncertainty and finish with upcoming catalysts. Keep sourced facts, "
                "analysis and scenarios visually and verbally distinct."
            )
        if self.archetype == "commercial":
            return (
                "Use a product-led commercial story: real problem, product demonstration, "
                "specific differentiator, proof that exists in the brief and a clear CTA "
                "only when requested. Avoid generic floating shapes and invented claims."
            )
        if self.archetype == "explainer":
            return (
                "Teach one concrete learning outcome using a real example, ordered mechanism, "
                "visual demonstration and practical conclusion. Every visual must clarify "
                "the lesson, not merely decorate the screen."
            )
        if self.archetype == "travel":
            return (
                "Use documentary travel pacing with location-specific environments, "
                "human activity, close details and geographic context. Avoid unrelated stock."
            )
        if self.archetype == "story":
            return (
                "Build a character-led narrative with a specific opening, turning point, "
                "consequence and meaningful ending. Use varied authentic visual evidence."
            )
        if self.archetype == "technology":
            return (
                "Explain the technology through real interfaces, hardware, processes, "
                "architecture and consequences. Keep diagrams accurate and visuals specific."
            )
        return (
            "Use subject-led editorial storytelling: a distinctive opening, a purposeful "
            "narrative progression, concrete evidence or example, and a memorable conclusion. "
            "Avoid generic stock phrases and repeated visual layouts."
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
    elif "--phonk" in lower or "--viral" in lower:
        archetype = "phonk"
    elif mode == "cinema" or "--movie" in lower or "--cinema" in lower:
        archetype = "cinema"
    elif (
        re.search(r"\b(?:market|markets|forex|xauusd|dxy|cpi|nfp|fomc|breaking news)\b", lower)
        and re.search(r"\b(?:today|aaj|latest|current|update|overview|outlook|session|news|calendar|right now|daily)\b", lower)
    ):
        archetype = "newsroom"
    elif re.search(r"\b(?:product|brand|campaign|advertisement|ad film|launch)\b", lower):
        archetype = "commercial"
    elif re.search(r"\b(?:tutorial|how to|guide|learn|explain|lesson)\b", lower):
        archetype = "explainer"
    elif re.search(r"\b(?:travel|destination|journey|city tour)\b", lower):
        archetype = "travel"
    elif re.search(r"\b(?:biography|true story|history|founder story)\b", lower):
        archetype = "story"
    elif re.search(r"\b(?:technology|software|ai|robot|science|coding)\b", lower):
        archetype = "technology"
    else:
        archetype = "editorial"

    fast_cuts = archetype in {"phonk", "meme"}
    scene_count = (
        max(10, min(14, round(duration_sec / 2.7)))
        if fast_cuts
        else max(7, min(12, round(duration_sec / 4.5)))
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
            f"Aim for approximately {plan.scene_count} scenes with roughly 2.5-second "
            "cuts, while keeping the final scene count between 10 and 14. Give every "
            "scene a distinct purpose, headline, and visual query. Keep the narration complete."
        )
    if plan.trending_context:
        parts.append(plan.trending_context)
    return "\n\n".join(part for part in parts if part)
