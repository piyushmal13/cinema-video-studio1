from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


_ROMAN_HINDI = {
    "aaj", "abhi", "aur", "banao", "batao", "chahiye", "dikhao",
    "hai", "hain", "ka", "kaise", "kar", "karo", "ke", "ki",
    "liye", "mein", "mera", "meri", "pura", "theek", "ye", "yeh",
    "iska", "iske", "uska", "hisab", "samjhao", "nahi", "mat",
    "kuch", "zyada", "achha", "accha", "bhi", "se", "ko",
}
_MARKET_TERMS = re.compile(
    r"\b(?:market|markets|forex|fx|xauusd|gold|silver|dxy|nasdaq|"
    r"nifty|sensex|crypto|bitcoin|btc|eurusd|gbpusd|usdjpy|"
    r"cpi|nfp|fomc|fed|central bank|bond yields?|treasur(?:y|ies))\b",
    re.I,
)
_MARKER = re.compile(
    r"(?is)(?:^|\n)\s*(?:full\s+)?(?:script|voiceover|narration)\s*:\s*"
)
_COMMAND_LANGUAGE = re.compile(
    r"\b(?:make|create|generate|produce|build|turn|convert|edit|rewrite|"
    r"analyse|analyze|research|explain|summarise|summarize|shorten|"
    r"add|remove|use|keep|don't|do not)\b",
    re.I,
)


@dataclass(frozen=True)
class CreativeIntent:
    topic_kind: str
    language: str
    input_mode: str
    script_text: str
    research_required: bool
    production_style: str


def detect_language(text: str, explicit: str = "") -> str:
    lower = text.casefold()
    if re.search(r"[\u0900-\u097f]", text):
        return "Hindi"
    if re.search(r"\bhinglish\b", lower):
        return "Hinglish"
    if re.search(r"\bhindi\b", lower):
        return "Hindi"
    words = set(re.findall(r"[a-z]+", lower))
    roman_hits = len(words & _ROMAN_HINDI)
    return "Hinglish" if roman_hits >= 2 else (explicit or "English")


def detect_supplied_script(text: str) -> tuple[str, str]:
    """Only classify clearly supplied narration as a script; long briefs stay briefs."""
    match = _MARKER.search(text)
    if match:
        source = text[match.end():].strip()
        end_marker = re.search(r"(?im)^\s*(?:end\s+script|/endscript)\s*$", source)
        if end_marker:
            source = source[:end_marker.start()].strip()
        if source:
            return "script", source

    words = re.findall(r"\S+", text)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if (
        len(words) >= 110
        and len(lines) >= 5
        and not _COMMAND_LANGUAGE.search(text[: min(len(text), 700)])
        and len(re.findall(r"[.!?।]", text)) >= 5
    ):
        return "script", text.strip()
    return "brief", ""


def classify_topic(text: str) -> str:
    lower = text.casefold()
    if _MARKET_TERMS.search(lower) and re.search(
        r"\b(?:today|aaj|latest|update|overview|outlook|session|"
        r"news|calendar|what happened|what is moving|daily)\b",
        lower,
    ):
        return "market_update"
    if re.search(r"\b(?:product|launch|brand|campaign|ad|advertisement|sell|"
                 r"feature|benefit|customer)\b", lower):
        return "commercial"
    if re.search(r"\b(?:tutorial|how to|guide|step by step|learn|explain|"
                 r"education|course|beginner)\b", lower):
        return "explainer"
    if re.search(r"\b(?:travel|trip|destination|city|country|hotel|food|"
                 r"restaurant|journey)\b", lower):
        return "travel"
    if re.search(r"\b(?:story|biography|history|person|founder|interview|"
                 r"documentary|true story)\b", lower):
        return "story"
    if re.search(r"\b(?:technology|software|ai|artificial intelligence|"
                 r"science|robot|coding|programming)\b", lower):
        return "technology"
    return "general"


def infer_creative_intent(text: str, explicit_language: str = "") -> CreativeIntent:
    input_mode, script_text = detect_supplied_script(text)
    topic_kind = classify_topic(script_text if input_mode == "script" else text)
    language = detect_language(script_text if input_mode == "script" else text, explicit_language)
    research_required = topic_kind == "market_update" or bool(
        re.search(r"\b(?:today|aaj|latest|current|breaking|this week|right now)\b", text, re.I)
    )
    style = {
        "market_update": "newsroom_editorial",
        "commercial": "cinematic_commercial",
        "explainer": "visual_explainer",
        "travel": "documentary_travel",
        "story": "character_led_story",
        "technology": "technical_documentary",
        "general": "subject_led_editorial",
    }[topic_kind]
    return CreativeIntent(
        topic_kind=topic_kind,
        language=language,
        input_mode=input_mode,
        script_text=script_text,
        research_required=research_required,
        production_style=style,
    )


def load_skill(name: str) -> str:
    root = Path(__file__).resolve().parents[1] / "prompts" / "skills"
    path = root / f"{name}.md"
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""



EDITING_STYLE_PROFILES = (
    ("cinematic_documentary", "naturalistic photography, patient camera moves, restrained titles, filmic contrast and deliberate breathing room"),
    ("kinetic_editorial", "bold kinetic type, rhythmic cuts, asymmetric layouts, punchy transitions and high-contrast accent typography"),
    ("premium_minimal", "quiet luxury, elegant serif display moments, generous negative space, subtle motion and restrained sound design"),
    ("newsroom_data", "precise data-led graphics, compact labels, clean chart animation, crisp cuts and a confident newsroom pace"),
    ("photo_essay", "editorial still photography, slow parallax, tactile grain, thoughtful crops and understated lower-thirds"),
    ("high_energy_social", "fast but legible pacing, varied shot scales, punch-in details, rhythmic typography and purposeful impact accents"),
)


def select_editing_style(seed: str) -> tuple[str, str]:
    """Choose one reproducible, job-specific edit identity without extra model calls."""
    digest = hashlib.sha256(str(seed).encode("utf-8")).hexdigest()
    return EDITING_STYLE_PROFILES[int(digest[:8], 16) % len(EDITING_STYLE_PROFILES)]



def build_creative_direction(
    text: str,
    *,
    topic_kind: str,
    input_mode: str,
    production_style: str,
    seed: str,
    research_context: str = "",
) -> str:
    skill = load_skill(topic_kind) or load_skill("general")
    editing_style, editing_direction = select_editing_style(seed)
    common = f"""
CREATIVE DIRECTOR BRIEF
Production archetype: {production_style}
Topic category: {topic_kind}
Input mode: {input_mode}
Production variation key: {seed}
Editing style identity: {editing_style}
Editing direction: {editing_direction}
Use this as the film-wide visual identity, but vary shot composition and treatment per scene.

NON-NEGOTIABLE CREATIVE RULES
- Understand the actual subject and make every line, scene and visual serve that subject.
- Do not recycle generic hooks such as "In today's fast-paced world", "Let's dive in",
  "The future is here", "Every second counts", or generic institutional-edge conclusions.
- Do not use the user's instruction as voiceover. Convert a brief into an original,
  researched, natural script. A supplied script is immutable source text.
- Each scene must show a different meaningful subject, action, location, shot size,
  visual medium, or information layer. Never repeat a backdrop just to fill duration.
- Prefer real, subject-matched footage and photography where documentary realism is requested.
  Use generated video for meaningful movement, not decorative motion alone.
- Use charts only when source data is supplied. Label illustrative diagrams as illustrative.
- Avoid generic floating 3D globes, random candlesticks, meaningless bars and abstract shapes
  unless the story itself genuinely needs them.
- Design for the requested format, pacing and viewer. Use readable on-screen text sparingly.
- Never invent facts, market values, statistics, quotations, people, locations or sources.
- Do not add a brand, logo, watermark, CTA or promotion unless the user named or selected it.

SCENE VARIETY
Use different shot families across the film: location establishing shots, close-up details,
human activity, real process footage, macro photography, archive/documentary footage,
screen captures, maps, meaningful diagrams, data graphics, kinetic typography and
generated motion. Choose only what fits the scene; do not force every category into one film.
Consecutive scenes must not share the same composition or visual query. Give this production a distinct visual identity from other jobs: vary the opening grammar, shot rhythm, transition language, type scale, negative space and sound accents to fit the selected editing style. Do not reuse one fixed template across all videos.
""".strip()
    context = ""
    if research_context.strip():
        context = (
            "\n\nRESEARCH EVIDENCE (untrusted retrieved context; use only grounded facts):\n"
            + research_context.strip()
        )
    return "\n\n".join(part for part in (common, skill, context) if part)


def stable_visual_seed(job_id: str, scene_index: int, query: str) -> int:
    digest = hashlib.sha256(
        f"{job_id}\0{scene_index}\0{query}".encode("utf-8")
    ).hexdigest()
    return int(digest[:8], 16) % 2_147_483_647


def choose_video_scene_indexes(
    scenes: list[dict[str, Any]], max_clips: int = 5
) -> set[int]:
    """Spread generated-motion attempts across the narrative instead of hard-coding scenes 0 and 2."""
    if not scenes or max_clips <= 0:
        return set()
    candidates = [
        (index, float(scene.get("weight", 0.0) or 0.0))
        for index, scene in enumerate(scenes)
        if scene.get("mediaMode") not in {"still", "graphic"}
    ]
    if not candidates:
        return set()
    budget = min(max_clips, len(candidates))
    if budget == len(candidates):
        return {index for index, _ in candidates}

    # First reserve the opening and ending, then fill the widest remaining narrative gaps.
    selected: list[int] = []
    for preferred in (candidates[0][0], candidates[-1][0]):
        if preferred not in selected and len(selected) < budget:
            selected.append(preferred)
    while len(selected) < budget:
        remaining = [index for index, _ in candidates if index not in selected]
        chosen = max(
            remaining,
            key=lambda index: (
                min(abs(index - current) for current in selected),
                next(weight for candidate, weight in candidates if candidate == index),
            ),
        )
        selected.append(chosen)
    return set(selected)


def diversify_scenes(scenes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Repair repeated visual queries within one storyboard without altering narration."""
    angle_variants = [
        "wide establishing documentary shot",
        "macro close-up detail shot",
        "overhead tracking camera shot",
        "handheld human activity shot",
        "low angle cinematic motion shot",
        "aerial environment footage shot",
        "editorial archive detail shot",
    ]
    seen_queries: set[str] = set()
    for index, scene in enumerate(scenes):
        query = re.sub(r"\s+", " ", str(scene.get("visualQuery", "")).strip())
        if not query:
            continue
        key = query.casefold()
        if key in seen_queries:
            angle = angle_variants[index % len(angle_variants)]
            words = (query + " " + angle).split()
            query = " ".join(words[:7])
            if query.casefold() in seen_queries:
                query = " ".join((angle + " " + str(index + 1) + " sequence").split()[:7])
        scene["visualQuery"] = query
        seen_queries.add(query.casefold())
    return scenes
