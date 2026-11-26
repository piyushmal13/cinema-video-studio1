import math
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class PromptIntent:
    prompt: str
    format: str
    mode: str
    duration_sec: int
    target_words: str
    min_narration_words: int
    voice: str
    lang_instruction: str
    brand: str
    color: str


def _requested_duration(prompt: str):
    duration_flag = re.search(
        r"--duration(?:=|\s+)(\d+(?:\.\d+)?)[\s-]*(seconds?|secs?|s|minutes?|mins?|m)?\b",
        prompt,
        re.IGNORECASE,
    )
    natural_duration = re.search(
        r"\b(\d+(?:\.\d+)?)[\s-]*(seconds?|secs?|minutes?|mins?)\b",
        prompt,
        re.IGNORECASE,
    )
    match = duration_flag or natural_duration
    if not match:
        return None

    value = float(match.group(1))
    unit = (match.group(2) or "seconds").lower()
    seconds = value * 60 if unit.startswith("m") else value
    return max(10, min(300, round(seconds)))


def parse_prompt_intent(prompt: str, format_hint: str = "vertical") -> PromptIntent:
    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError("A non-empty Telegram prompt is required.")
    if format_hint not in {"vertical", "landscape"}:
        raise ValueError("Format must be 'vertical' or 'landscape'.")

    original = prompt.strip()
    lower = original.lower()
    movie_command = bool(re.match(r"^/(?:movie|cinema)(?:@\w+)?\b", lower))
    is_landscape = bool(
        movie_command
        or re.search(r"--(?:movie|cinema|landscape)\b", lower)
        or re.search(r"\b(?:landscape|widescreen|horizontal|16\s*:\s*9)\b", lower)
    )
    is_vertical = bool(
        re.search(r"--(?:portrait|vertical|reel)\b", lower)
        or re.search(r"\b(?:portrait|vertical|9\s*:\s*16|reel|shorts?)\b", lower)
    )
    video_command = bool(re.match(r"^/(?:video|reel)(?:@\w+)?\b", lower))
    cinematic_request = bool(
        re.search(r"\b(?:movie|documentary|mini[- ]film|cinema film|featurette)\b", lower)
    )

    if is_landscape:
        video_format = "landscape"
    elif is_vertical:
        video_format = "vertical"
    elif video_command:
        video_format = format_hint
    else:
        video_format = format_hint

    mode = "cinema" if video_format == "landscape" or movie_command or cinematic_request else "shorts"
    default_duration = 75 if video_format == "landscape" else 45
    duration_sec = _requested_duration(original) or default_duration

    if re.search(r"\bhinglish\b", lower):
        language = "Hinglish"
        voice = "hi-IN-MadhurNeural"
    elif re.search(r"\bhindi\b", lower):
        language = "Hindi"
        voice = "hi-IN-MadhurNeural"
    else:
        language = "English"
        voice = "en-US-AndrewMultilingualNeural"

    if re.search(r"\b(?:female|woman|women)\s+(?:voice|voiceover|narrator|narration)\b|\b(?:voice|voiceover|narrator|narration)\s+(?:female|woman)\b|--female\b", lower):
        voice = "hi-IN-SwaraNeural" if language != "English" else "en-US-AvaMultilingualNeural"

    brand = "IFXTRADES"
    brand_match = re.search(
        r"--brand(?:=|\s+)(?:\"([^\"]+)\"|'([^']+)'|([A-Za-z0-9_-]+))",
        original,
        re.IGNORECASE,
    )
    if brand_match:
        brand = next(group for group in brand_match.groups() if group).strip().upper()
        if len(brand) > 32:
            raise ValueError("Brand names must be 32 characters or fewer.")

    color = "#D4AF37"
    color_match = re.search(r"--color=([^\s]+)", original, re.IGNORECASE)
    if color_match:
        requested_color = color_match.group(1)
        if not re.fullmatch(r"#[0-9A-Fa-f]{6}", requested_color):
            raise ValueError("Color must use the #RRGGBB format.")
        color = requested_color.upper()

    cleaned = re.sub(r"^/(?:video|movie|cinema|reel)(?:@\w+)?\s*", "", original, flags=re.IGNORECASE)
    cleaned = re.sub(
        r"--(?:movie|cinema|landscape|portrait|vertical|reel|hindi|hinglish|female|phonk|viral|meme|trending)\b",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        r"--brand(?:=|\s+)(?:\"[^\"]+\"|'[^']+'|[A-Za-z0-9_-]+)",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"--color=[^\s]+", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(
        r"--duration(?:=|\s+)\d+(?:\.\d+)?\s*(?:seconds?|secs?|s|minutes?|mins?|m)?\b",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if not cleaned:
        raise ValueError("Add a topic, story, or script after the video settings.")

    word_count = round(duration_sec * 2.4)
    min_words = max(30, round(word_count * 0.9))
    max_words = max(min_words + 5, round(word_count * 1.12))
    target_words = (
        f"{min_words} to {max_words} words (approximately {duration_sec} seconds)"
    )

    return PromptIntent(
        prompt=cleaned,
        format=video_format,
        mode=mode,
        duration_sec=duration_sec,
        target_words=target_words,
        min_narration_words=min_words,
        voice=voice,
        lang_instruction=(
            f"Write the narration in dramatic, authoritative, cinematic {language}. "
            "Keep names, numbers, and technical terms clear for neural voice narration."
        ),
        brand=brand,
        color=color,
    )


def validate_storyboard(
    storyboard: dict,
    min_narration_words: int,
    scene_count_range: tuple[int, int] = (5, 7),
) -> dict:
    if not isinstance(storyboard, dict):
        raise ValueError("The AI response must be a JSON object.")

    narration = storyboard.get("narration")
    scenes = storyboard.get("scenes")
    if not isinstance(narration, str) or not narration.strip():
        raise ValueError("The AI response is missing narration.")
    word_count = len(narration.split())
    if word_count < min_narration_words:
        raise ValueError(
            f"Narration is too short: {word_count} words; "
            f"at least {min_narration_words} are required."
        )
    min_scenes, max_scenes = scene_count_range
    if not isinstance(scenes, list) or not min_scenes <= len(scenes) <= max_scenes:
        if min_scenes == max_scenes:
            requirement = f"exactly {min_scenes}"
        else:
            requirement = f"{min_scenes} to {max_scenes}"
        raise ValueError(f"The AI response must contain {requirement} scenes.")

    valid_types = {
        "cinema_hero",
        "three_d_globe",
        "three_d_bars",
        "candlestick_chart",
        "split_compare",
        "step_list",
        "cinema_outro",
    }
    valid_motions = {"zoom_in", "zoom_out", "pan_left", "pan_right", "dolly_push"}
    valid_cues = {"boom", "whoosh", "riser", "pulse"}
    for index, scene in enumerate(scenes):
        if not isinstance(scene, dict):
            raise ValueError(f"Scene {index + 1} must be a JSON object.")
        if scene.get("type") not in valid_types:
            raise ValueError(f"Scene {index + 1} has an unsupported scene type.")
        for field in ("headline", "kicker", "visualQuery"):
            if not isinstance(scene.get(field), str) or not scene[field].strip():
                raise ValueError(f"Scene {index + 1} is missing {field}.")
        query_words = scene["visualQuery"].split()
        if not 4 <= len(query_words) <= 7:
            raise ValueError(f"Scene {index + 1} visualQuery must contain 4 to 7 words.")
        if scene.get("cameraMotion") not in valid_motions:
            raise ValueError(f"Scene {index + 1} has an unsupported camera motion.")
        if scene.get("sfxCue") not in valid_cues:
            raise ValueError(f"Scene {index + 1} has an unsupported sound cue.")
        weight = scene.get("weight")
        if isinstance(weight, bool) or not isinstance(weight, (int, float)):
            raise ValueError(f"Scene {index + 1} weight must be a number.")
        if not math.isfinite(weight) or weight <= 0:
            raise ValueError(f"Scene {index + 1} weight must be a positive finite number.")

        bars = scene.get("barValues")
        if bars is not None:
            if not isinstance(bars, list) or not bars:
                raise ValueError(f"Scene {index + 1} barValues must be a non-empty list.")
            for bar in bars:
                if (
                    not isinstance(bar, dict)
                    or not isinstance(bar.get("label"), str)
                    or isinstance(bar.get("value"), bool)
                    or not isinstance(bar.get("value"), (int, float))
                    or not math.isfinite(bar["value"])
                    or bar["value"] < 0
                ):
                    raise ValueError(f"Scene {index + 1} contains invalid chart data.")

    return storyboard


def compose_story_prompt(prompt: str, previous_context: str = "") -> str:
    if not previous_context.strip():
        return prompt
    return (
        "Earlier requests from this Telegram chat are included only as context. "
        "Use them only when the latest request clearly refers back to them. "
        "The latest request is authoritative and overrides conflicting earlier details.\n\n"
        f"Earlier requests:\n{previous_context.strip()}\n\n"
        f"Latest request:\n{prompt}"
    )
