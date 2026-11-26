import asyncio
import hashlib
import html
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unicodedata
import urllib.parse

import requests
import edge_tts
from gtts import gTTS
if __package__:
    from .prompt_intent import compose_story_prompt, parse_prompt_intent, validate_storyboard
    from .viral_engineer import (
        build_viral_plan,
        enhance_story_prompt,
        fetch_trending_context,
        strip_viral_flags,
    )
    from .longform_director import documentary_direction
    from .research_director import route_production_request
    from .media_cache import MediaAssetCache
    from .setup_real_audio import SFX_VARIANTS, ensure_audio_assets
else:
    from prompt_intent import compose_story_prompt, parse_prompt_intent, validate_storyboard
    from viral_engineer import (
        build_viral_plan,
        enhance_story_prompt,
        fetch_trending_context,
        strip_viral_flags,
    )
    from longform_director import documentary_direction
    from research_director import route_production_request
    from media_cache import MediaAssetCache
    from setup_real_audio import SFX_VARIANTS, ensure_audio_assets

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
RAW_PROMPT = os.environ.get("PROMPT", "Create a cinematic short film on how AI is transforming global finance").strip()

os.makedirs("public/media", exist_ok=True)
os.makedirs("out", exist_ok=True)

SYSTEM_PROMPT = """You are an Academy-Award-caliber film director and motion-graphics creative director.
Given a user topic, story idea, or full script, craft a complete {target_words} production script and {scene_count_instruction} distinct scenes.
{lang_instruction}
{style_instruction}
Use brandTag "{brand}", themeColor "{color}", and mode "{mode}".

Treat the user's brief as the source of truth. For a topic, create a clear beginning, explanation with useful context, concrete example, and satisfying ending. For a supplied script, preserve its key facts and intended meaning; do not replace it with a generic summary. Explain technical ideas in plain language, avoid filler, and do not invent statistics, quotations, or claims. Keep the narration complete enough for the requested runtime. Do not speak production settings or visual directions in the voiceover.
The narration MUST contain at least {min_narration_words} whitespace-separated words. This is a hard minimum, not a suggestion.

Return ONLY one valid JSON object with these top-level keys:
- "title": concise title specific to the user's brief.
- "narration": complete spoken voiceover, with no hashtags, emojis, or stage directions.
- "scenes": an array containing the requested number of scene objects. Every object must include:
  "type", "weight", "kicker", "headline", "visualQuery", "cameraMotion", and "sfxCue".
  Optional fields are "subline", "leftLabel", "rightLabel", and "barValues".

Do not copy generic sample content. Every title, scene label, headline, visual query,
and optional detail must be specific to the user's request. Never invent statistics:
only include chart values when the user supplied them or clearly label them as hypothetical.

Available scene types: "cinema_hero", "three_d_globe", "three_d_bars", "candlestick_chart", "split_compare", "step_list", "cinema_outro".
Rules:
1. Every scene MUST include a vivid 4-to-7 word English "visualQuery".
2. Choose "cameraMotion" from: "zoom_in", "zoom_out", "pan_left", "pan_right", "dolly_push".
3. Choose "sfxCue" from: "boom", "whoosh", "pulse".
4. Weights must be positive and sum to 1.0.
5. Build a clear beginning, middle, and ending across the scene sequence."""

def clean_json_response(raw_text: str) -> dict:
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw_text.strip(), flags=re.MULTILINE)
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end != -1:
        cleaned = cleaned[start : end + 1]
    return json.loads(cleaned)


def build_fallback_storyboard(
    prompt: str,
    brand: str,
    color: str,
    mode: str,
    is_hinglish: bool,
    min_words: int = 60,
) -> dict:
    latest_request = re.search(
        r"Latest request:\s*(.*?)(?:\n\n|$)", prompt, re.IGNORECASE | re.DOTALL
    )
    brief = latest_request.group(1) if latest_request else prompt.split("\n\n", 1)[0]
    brief = re.sub(r"/(?:video|movie|cinema|reel)(?:@\w+)?", " ", brief, flags=re.IGNORECASE)
    brief = re.sub(r"--[\w=-]+", " ", brief)
    brief = re.sub(
        r"^\s*(?:please\s+)?(?:explain|create|make|write|generate|produce|show|tell me about)\s+",
        "",
        brief,
        flags=re.IGNORECASE,
    )
    brief = re.sub(
        r"^\s*(?:how|why|what|a|an|the|short|viral|video|film|reel|about|on)\s+",
        "",
        brief,
        flags=re.IGNORECASE,
    )
    brief = re.sub(r"\b\d+(?:\.\d+)?[\s-]*(?:seconds?|secs?|minutes?|mins?)\b", " ", brief, flags=re.IGNORECASE)
    topic_words = re.findall(r"[\w'-]+", brief, flags=re.UNICODE)[:8]
    topic = " ".join(topic_words) or "the core idea"

    if is_hinglish:
        narration_parts = [
            f"Aaj hum {topic} ko seedhe samjhenge, bina bade claims ya shortcut ke.",
            "Pehle core idea ko simple language mein define karein, aur facts ko assumptions se alag rakhein.",
            "Phir process ko step by step follow karein, taaki har decision ka connection clear ho.",
            "Ek practical example mechanism samjhata hai, bina numbers invent kiye ya outcome promise kiye.",
            "Kisi bhi decision se pehle signal, constraint, aur trade-off ko saath mein dekhein.",
            "Institutional edge disciplined reasoning hai: evidence check karein, alternatives compare karein, uncertainty clear rakhein.",
            "Information badle toh conclusion ko update karein, purane view ko force na karein.",
            "Takeaway simple hai: mechanism samjhein, assumptions test karein, aur next step soch samajh kar lein.",
        ]
        extensions = [
            f"{topic} ko evidence, timing, incentives, aur risk ke lens se dobara dekhein.",
            "Jo unknown hai use clearly name karein, aur unsupported certainty se bachein.",
            "Har alternative ko same standard se compare karein, phir conclusion ko calmly update karein.",
        ]
    else:
        narration_parts = [
            f"This film examines {topic} by starting with the real question, not a dramatic claim or shortcut.",
            "First, define the core idea in plain language and separate verified details from assumptions.",
            "Next, follow the process step by step so viewers can see how each decision connects.",
            "A useful example makes the mechanism easier to understand without inventing numbers or promising an outcome.",
            "Look for the signal, the constraint, and the trade-off before deciding what deserves attention.",
            "The institutional edge is disciplined reasoning: check evidence, compare alternatives, and keep uncertainty visible.",
            "If the information changes, revisit the conclusion instead of defending a view that no longer fits.",
            "The takeaway is practical: understand the mechanism, test assumptions, and make the next move deliberately.",
        ]
        extensions = [
            f"Revisit {topic} through evidence, timing, incentives, and risk, while naming what remains unknown.",
            "Compare each alternative using the same standard, then update the conclusion when the evidence changes.",
            "A careful review separates a useful signal from an assumption and keeps the next question visible.",
        ]

    narration = " ".join(narration_parts)
    extension_index = 0
    target_words = max(60, min_words)
    while len(narration.split()) < target_words:
        narration += " " + extensions[extension_index % len(extensions)]
        extension_index += 1

    scene_specs = [
        ("cinema_hero", "THE QUESTION", "START WITH THE CORE IDEA", "central idea emerging through cinematic shadows", "dolly_push", "boom"),
        ("three_d_globe", "THE CONTEXT", "CONNECT THE BIG PICTURE", "global network linking ideas across borders", "pan_left", "whoosh"),
        ("three_d_bars", "THE MECHANISM", "FOLLOW EACH STEP", "process diagram illuminated in a dark studio", "zoom_in", "pulse"),
        ("candlestick_chart", "THE SIGNAL", "SEPARATE SIGNAL FROM NOISE", "animated market candles crossing liquidity zones", "pan_right", "whoosh"),
        ("split_compare", "THE TRADE-OFF", "COMPARE THE ALTERNATIVES", "two contrasting strategies under focused light", "zoom_out", "pulse"),
        ("step_list", "THE STANDARD", "TEST THE ASSUMPTIONS", "evidence checklist beside a research notebook", "dolly_push", "whoosh"),
        ("three_d_globe", "THE DECISION", "MAKE THE NEXT MOVE", "risk controls shaping deliberate decisions", "pan_left", "pulse"),
        ("three_d_bars", "THE EXAMPLE", "MAKE THE MECHANISM VISIBLE", "hands reviewing evidence under studio light", "zoom_in", "pulse"),
        ("three_d_globe", "THE TIMELINE", "FOLLOW WHAT CHANGES NEXT", "measured timeline connecting changing incentives", "pan_right", "whoosh"),
        ("split_compare", "THE ALTERNATIVES", "WEIGH THE REAL OPTIONS", "clear decision tree among open alternatives", "dolly_push", "pulse"),
        ("step_list", "THE IMPLICATION", "NAME THE PRACTICAL CONSEQUENCE", "research notes beside a focused market display", "pan_left", "whoosh"),
        ("cinema_outro", "THE TAKEAWAY", "RETURN TO THE CORE IDEA", "quiet sunrise over a cinematic city skyline", "zoom_out", "boom"),
    ]
    scenes = [
        {
            "type": scene_type,
            "weight": 1.0,
            "kicker": kicker,
            "headline": headline,
            "subline": f"A focused look at {topic}." if index in {0, len(scene_specs) - 1} else "",
            "visualQuery": visual_query,
            "cameraMotion": motion,
            "sfxCue": cue,
        }
        for index, (scene_type, kicker, headline, visual_query, motion, cue)
        in enumerate(scene_specs)
    ]
    return {
        "title": f"{topic.title()} | Signal to Strategy",
        "brandTag": brand,
        "themeColor": color,
        "mode": mode,
        "narration": narration,
        "scenes": scenes,
    }


def generate_storyboard(
    prompt: str,
    sys_prompt: str,
    min_narration_words: int,
    brand: str = "IFXTRADES",
    color: str = "#D4AF37",
    mode: str = "shorts",
    is_hinglish: bool = False,
) -> dict:
    minimum_words = max(60, min_narration_words)
    # Primary: keyless Pollinations. Its public free tier can impose cooldowns.
    pollinations_error = None
    free_model = "openai"
    retry_prompt = f"{prompt}\n\nRespond with valid JSON only."
    for attempt in range(2):
        try:
            resp = requests.post(
                "https://text.pollinations.ai/openai",
                headers={"Content-Type": "application/json"},
                json={
                    "model": free_model,
                    "messages": [
                        {"role": "system", "content": sys_prompt},
                        {"role": "user", "content": retry_prompt},
                    ],
                    "temperature": 0.5,
                    "max_tokens": 8192,
                    "response_format": {"type": "json_object"},
                },
                timeout=75,
            )
        except Exception as e:
            print(f"Pollinations {free_model} fallback: {e}")
            pollinations_error = str(e)
            if attempt == 0:
                time.sleep(46)
                continue
            break

        if (
            resp.status_code == 402
            and "FREE_LIMIT" in resp.text
            and attempt == 0
        ):
            retry_after = re.search(r"retry after\s+(\d+)s", resp.text, re.IGNORECASE)
            delay = min(int(retry_after.group(1)) + 1, 61) if retry_after else 46
            print(f"Pollinations free limit reached; retrying after {delay}s.")
            time.sleep(delay)
            continue
        if resp.status_code != 200:
            pollinations_error = f"HTTP {resp.status_code}: {resp.text[:200]}"
            print(f"Pollinations {free_model} status {resp.status_code}: {resp.text[:200]}")
            break

        try:
            raw_text = resp.json()["choices"][0]["message"]["content"]
            storyboard = validate_storyboard(
                clean_json_response(raw_text),
                minimum_words,
            )
            print(f"Directed with Pollinations Free ({free_model})")
            return storyboard
        except (IndexError, KeyError, TypeError, ValueError) as e:
            pollinations_error = str(e)
            print(f"Pollinations {free_model} response rejected: {e}")
            if attempt == 0:
                retry_prompt = (
                    f"{prompt}\n\nThe previous response was rejected: {e}. "
                    f"Return a complete corrected JSON object. The narration must "
                    f"contain at least {minimum_words} words and include "
                    "between 3 and 14 complete scenes. Do not shorten it."
                )
                time.sleep(46)

    if GEMINI_API_KEY:
        for model_id in ["gemini-3.8-flash", "gemini-3.5-flash-lite", "gemini-3-flash-preview"]:
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_id}:generateContent"
                resp = requests.post(
                    url,
                    headers={
                        "Content-Type": "application/json",
                        "x-goog-api-key": GEMINI_API_KEY,
                    },
                    json={
                        "contents": [{"parts": [{"text": f"{sys_prompt}\n\nUser request: {prompt}"}]}],
                        "generationConfig": {"responseMimeType": "application/json", "temperature": 0.5},
                    },
                    timeout=60,
                )
                if resp.status_code == 200:
                    raw_text = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
                    print(f"Directed with Gemini fallback ({model_id})")
                    return validate_storyboard(
                        clean_json_response(raw_text),
                        minimum_words,
                    )
                print(f"Gemini {model_id} status {resp.status_code}: {resp.text[:200]}")
            except Exception as e:
                print(f"Gemini {model_id} error: {e}")

    detail = f" Pollinations error: {pollinations_error}" if pollinations_error else ""
    print(f"AI storyboard providers unavailable; using deterministic fallback.{detail}")
    fallback = build_fallback_storyboard(
        prompt,
        brand,
        color,
        mode,
        is_hinglish,
        min_words=minimum_words,
    )
    return validate_storyboard(fallback, minimum_words)


_GRADIO_VIDEO_SCRIPT = r"""
import os
import shutil
import sys
import requests
from gradio_client import Client

space, prompt, width, height, output_path, timeout = sys.argv[1:]
timeout = float(timeout)
client = Client(
    space,
    httpx_kwargs={"timeout": timeout},
    verbose=False,
    analytics_enabled=False,
)
job = client.submit(
    prompt,
    "blurry, distorted, flicker, captions, text, watermark",
    None,
    None,
    int(height),
    int(width),
    "text-to-video",
    2.0,
    9,
    42,
    True,
    1.0,
    False,
    api_name="/text_to_video",
)
result = job.result(timeout=timeout)
video = result[0] if isinstance(result, (tuple, list)) else result
if isinstance(video, dict):
    video = video.get("path") or video.get("url")
if hasattr(video, "path"):
    video = video.path
if not isinstance(video, str) or not video:
    raise RuntimeError("The Gradio Space returned no video path.")
if video.startswith(("http://", "https://")):
    response = requests.get(video, timeout=min(timeout, 12))
    response.raise_for_status()
    if len(response.content) <= 50000 or b"ftyp" not in response.content[:32]:
        raise RuntimeError("The Gradio Space returned an invalid or undersized MP4.")
    with open(output_path, "wb") as target:
        target.write(response.content)
else:
    if not os.path.isfile(video):
        raise RuntimeError("The Gradio Space output file is missing.")
    shutil.copyfile(video, output_path)
"""


def _is_valid_mp4(path: str) -> bool:
    if not os.path.isfile(path) or os.path.getsize(path) <= 50_000:
        return False
    with open(path, "rb") as video_file:
        if b"ftyp" not in video_file.read(32):
            return False
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return True
    try:
        result = subprocess.run(
            [
                ffprobe,
                "-v",
                "error",
                "-show_entries",
                "format=format_name",
                "-of",
                "default=nw=1:nk=1",
                path,
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=8,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0 and "mp4" in result.stdout.lower()


def try_generate_ai_video_clip(
    prompt: str,
    idx: int,
    orientation: str,
    out_mp4: str,
) -> bool:
    if idx not in {0, 2}:
        return False
    cache = MediaAssetCache()
    cached = cache.get(prompt, orientation, expected_kind="video")
    if cached:
        cached_path, _ = cached
        os.makedirs(os.path.dirname(out_mp4) or ".", exist_ok=True)
        shutil.copyfile(cached_path, out_mp4)
        print(f"Using cached motion clip for scene {idx}.")
        return True

    deadline = time.monotonic() + 45
    width, height = (832, 480) if orientation == "landscape" else (480, 832)
    encoded_prompt = urllib.parse.quote(
        f"{prompt}, cinematic camera motion, coherent subject movement, no text",
        safe="",
    )
    model = os.environ.get("CINEMA_POLLINATIONS_VIDEO_MODEL", "wan")
    video_url = (
        f"https://video.pollinations.ai/prompt/{encoded_prompt}"
        f"?model={urllib.parse.quote(model)}&width={width}&height={height}"
    )

    try:
        response = requests.get(
            video_url,
            headers={"Accept": "video/mp4"},
            timeout=(4, min(15, max(1, deadline - time.monotonic()))),
        )
        if response.status_code == 200 and len(response.content) <= 80_000_000:
            os.makedirs(os.path.dirname(out_mp4) or ".", exist_ok=True)
            with open(out_mp4, "wb") as output_file:
                output_file.write(response.content)
            if _is_valid_mp4(out_mp4):
                cache.store(prompt, orientation, out_mp4, "video")
                print(f"Generated scene {idx} video with Pollinations.")
                return True
        print(f"Pollinations video unavailable for scene {idx}: HTTP {response.status_code}.")
    except (requests.RequestException, OSError) as error:
        print(f"Pollinations video unavailable for scene {idx}: {error}")
    if os.path.isfile(out_mp4):
        os.remove(out_mp4)

    remaining = deadline - time.monotonic()
    if remaining <= 1:
        return False
    try:
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                _GRADIO_VIDEO_SCRIPT,
                os.environ.get(
                    "CINEMA_LTX_SPACE",
                    "Lightricks/ltx-video-distilled",
                ),
                prompt,
                str(width),
                str(height),
                out_mp4,
                str(max(1, int(remaining))),
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=remaining,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        print(f"Gradio video generation timed out or failed for scene {idx}: {error}")
        if os.path.isfile(out_mp4):
            os.remove(out_mp4)
        return False

    if result.returncode == 0 and _is_valid_mp4(out_mp4):
        cache.store(prompt, orientation, out_mp4, "video")
        print(f"Generated scene {idx} video with Hugging Face ZeroGPU.")
        return True
    if os.path.isfile(out_mp4):
        os.remove(out_mp4)
    detail = result.stderr.strip().splitlines()[-1:] if result.stderr else []
    print(
        f"Hugging Face video unavailable for scene {idx}"
        + (f": {detail[0][:240]}" if detail else ".")
    )
    return False


_VISUAL_STOP_WORDS = {
    "a", "an", "and", "at", "by", "for", "from", "in", "into", "of", "on",
    "over", "the", "through", "to", "under", "with", "cinematic", "photorealistic",
    "realistic", "wide", "close", "shot", "studio", "light", "lighting",
}
_REJECT_MEDIA_TERMS = re.compile(
    r"\b(?:anime|cartoon|illustration|clip[ -]?art|vector|icon|logo|"
    r"portrait|headshot|manga|drawing)\b",
    re.IGNORECASE,
)


def _visual_subject_terms(query: str) -> list[str]:
    terms = [
        term.lower()
        for term in re.findall(r"[A-Za-z][A-Za-z0-9-]{2,}", query)
        if term.lower() not in _VISUAL_STOP_WORDS
    ]
    return list(dict.fromkeys(terms))[:5]


def _matches_visual_subject(title: str, query: str) -> bool:
    if _REJECT_MEDIA_TERMS.search(title):
        return False
    terms = _visual_subject_terms(query)
    return bool(terms) and any(term in title.lower() for term in terms)


def _license_is_reusable(metadata: dict) -> bool:
    values = [
        metadata.get("licenseurl", ""),
        metadata.get("rights", ""),
        metadata.get("LicenseShortName", ""),
    ]
    for value in values:
        if isinstance(value, dict):
            value = value.get("value", "")
        plain = re.sub(r"<[^>]+>", " ", str(value)).lower()
        if "public domain" in plain or "cc0" in plain or "creativecommons.org/publicdomain/zero" in plain:
            return True
    return False


def _download_bounded(url: str, output_path: str, maximum_bytes: int = 15 * 1024 * 1024) -> bool:
    response = requests.get(
        url,
        headers={"User-Agent": "CinemaVideoStudio/1.0 (public-domain media fetcher)"},
        stream=True,
        timeout=(4, 10),
    )
    response.raise_for_status()
    declared_length = response.headers.get("Content-Length")
    if declared_length and int(declared_length) > maximum_bytes:
        return False

    written = 0
    try:
        with open(output_path, "wb") as output_file:
            iterator = getattr(response, "iter_content", None)
            chunks = iterator(chunk_size=64 * 1024) if callable(iterator) else [response.content]
            for chunk in chunks:
                if not chunk:
                    continue
                written += len(chunk)
                if written > maximum_bytes:
                    return False
                output_file.write(chunk)
    finally:
        close = getattr(response, "close", None)
        if callable(close):
            close()
    return written > 0


def _trim_video_clip(source_path: str, output_path: str, orientation: str) -> bool:
    width, height = (832, 480) if orientation == "landscape" else (480, 832)
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    try:
        subprocess.run(
            [
                _ffmpeg_executable(), "-y", "-i", source_path, "-t", "5",
                "-map", "0:v:0", "-vf",
                f"scale={width}:{height}:force_original_aspect_ratio=increase,"
                f"crop={width}:{height}",
                "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
                "-movflags", "+faststart", output_path,
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError) as error:
        print(f"Could not trim public-domain video: {error}")
        return False
    return _is_valid_mp4(output_path)


def try_archive_org_video(
    query: str,
    idx: int,
    orientation: str,
    out_mp4: str,
) -> bool:
    if os.environ.get("CINEMA_OFFLINE") == "1":
        return False
    terms = _visual_subject_terms(query)
    if not terms:
        return False
    search_terms = " OR ".join(f"title:{term} OR subject:{term}" for term in terms[:3])
    try:
        response = requests.get(
            "https://archive.org/advancedsearch.php",
            params={
                "q": f"mediatype:movies AND ({search_terms})",
                "fl[]": ["identifier"],
                "rows": 5,
                "page": 1,
                "output": "json",
            },
            headers={"User-Agent": "CinemaVideoStudio/1.0"},
            timeout=(4, 8),
        )
        response.raise_for_status()
        documents = response.json().get("response", {}).get("docs", [])
        os.makedirs(os.path.dirname(out_mp4) or ".", exist_ok=True)
        for document in documents:
            identifier = document.get("identifier", "")
            if not re.fullmatch(r"[A-Za-z0-9._-]{1,120}", identifier):
                continue
            metadata_response = requests.get(
                f"https://archive.org/metadata/{identifier}",
                headers={"User-Agent": "CinemaVideoStudio/1.0"},
                timeout=(4, 8),
            )
            metadata_response.raise_for_status()
            metadata = metadata_response.json()
            if not _license_is_reusable(metadata.get("metadata", {})):
                continue
            candidates = [
                entry for entry in metadata.get("files", [])
                if isinstance(entry.get("name"), str)
                and entry["name"].lower().endswith(".mp4")
                and 0 < int(entry.get("size", 0) or 0) <= 15 * 1024 * 1024
            ]
            for entry in sorted(candidates, key=lambda item: int(item.get("size", 0))):
                encoded_name = urllib.parse.quote(entry["name"], safe="")
                source_url = f"https://archive.org/download/{identifier}/{encoded_name}"
                with tempfile.TemporaryDirectory() as temp_dir:
                    source_path = os.path.join(temp_dir, "archive-source.mp4")
                    if not _download_bounded(source_url, source_path):
                        continue
                    if _trim_video_clip(source_path, out_mp4, orientation):
                        print(f"Using Archive.org public-domain clip for scene {idx}: {identifier}")
                        return True
    except (requests.RequestException, ValueError, TypeError, OSError) as error:
        print(f"Archive.org video search failed for scene {idx}: {error}")
    return False


def _commons_pages(query: str, filetype: str, orientation: str = "landscape") -> dict:
    response = requests.get(
        "https://commons.wikimedia.org/w/api.php",
        params={
            "action": "query",
            "generator": "search",
            "gsrsearch": f"filetype:{filetype} {query}",
            "gsrnamespace": 6,
            "gsrlimit": 6,
            "prop": "imageinfo",
            "iiprop": "url|extmetadata|size",
            "iiurlwidth": 1280 if orientation == "landscape" else 768,
            "format": "json",
        },
        headers={"User-Agent": "CinemaVideoStudio/1.0 (Wikimedia Commons media search)"},
        timeout=(4, 8),
    )
    response.raise_for_status()
    return response.json().get("query", {}).get("pages", {})


def _commons_license(image_info: dict) -> tuple[bool, str]:
    metadata = image_info.get("extmetadata", {})
    license_meta = metadata.get("LicenseShortName", {})
    license_name = re.sub(
        r"<[^>]+>", "", str(license_meta.get("value", ""))
    ).strip().lower()
    return license_name in {"cc0", "public domain"}, license_name


def try_wikimedia_video(
    query: str,
    idx: int,
    orientation: str,
    out_mp4: str,
) -> bool:
    if os.environ.get("CINEMA_OFFLINE") == "1":
        return False
    try:
        for page in _commons_pages(query, "video").values():
            title = str(page.get("title", ""))
            if not _matches_visual_subject(title, query):
                continue
            image_info = (page.get("imageinfo") or [{}])[0]
            reusable, license_name = _commons_license(image_info)
            media_url = image_info.get("url")
            if not reusable or not media_url:
                continue
            with tempfile.TemporaryDirectory() as temp_dir:
                source_path = os.path.join(temp_dir, "commons-source")
                if not _download_bounded(media_url, source_path):
                    continue
                if _trim_video_clip(source_path, out_mp4, orientation):
                    print(
                        f"Using Wikimedia Commons {license_name} video for scene {idx}: {title}"
                    )
                    return True
    except (requests.RequestException, ValueError, TypeError, OSError) as error:
        print(f"Wikimedia Commons video search failed for scene {idx}: {error}")
    return False


def _fetch_wikimedia_photo(query: str, idx: int, orientation: str) -> tuple[str, str]:
    for page in _commons_pages(query, "bitmap", orientation).values():
        title = str(page.get("title", ""))
        if not _matches_visual_subject(title, query) or title.lower().endswith(".svg"):
            continue
        image_info = (page.get("imageinfo") or [{}])[0]
        reusable, license_name = _commons_license(image_info)
        image_url = image_info.get("thumburl") or image_info.get("url")
        if not reusable or not image_url or image_url.lower().split("?")[0].endswith(".svg"):
            continue
        image_response = requests.get(
            image_url,
            headers={"User-Agent": "CinemaVideoStudio/1.0"},
            timeout=(4, 8),
        )
        image_response.raise_for_status()
        content_type = image_response.headers.get("Content-Type", "").lower()
        if len(image_response.content) <= 5000 or content_type not in {
            "image/jpeg", "image/png", "image/webp",
        }:
            continue
        suffix = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}[content_type]
        relative_path = f"media/scene_{idx}_photo{suffix}"
        path = os.path.join("public", relative_path.replace("/", os.sep))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as image_file:
            image_file.write(image_response.content)
        print(f"Using Wikimedia Commons {license_name} photo for scene {idx}: {title}")
        return relative_path, "image"
    return "", "none"


def _fetch_broll_or_ai_visual_uncached(query: str, idx: int, orientation: str):
    if os.environ.get("CINEMA_OFFLINE") == "1":
        return "", "none"
    clip_path = os.path.join("public", "media", f"scene_{idx}_stock.mp4")
    if try_archive_org_video(query, idx, orientation, clip_path):
        return f"media/scene_{idx}_stock.mp4", "video"
    if try_wikimedia_video(query, idx, orientation, clip_path):
        return f"media/scene_{idx}_stock.mp4", "video"

    try:
        width, height = (1280, 720) if orientation == "landscape" else (768, 1344)
        subjects = ", ".join(_visual_subject_terms(query))
        locked_prompt = (
            f"Photorealistic documentary cinematography of exactly {subjects}; "
            f"the visible subject must directly match {subjects}. {query}. "
            "Natural photographic detail, physically plausible light, real camera optics, "
            "high contrast obsidian and warm gold grade. NEGATIVE: NO anime, NO cartoon, "
            "NO illustration, NO random portrait, NO text, NO watermark, NO logo, "
            "NO collage, NO clip-art, NO unrelated subject."
        )
        encoded_prompt = urllib.parse.quote(locked_prompt, safe="")
        image_url = (
            f"https://image.pollinations.ai/prompt/{encoded_prompt}"
            f"?width={width}&height={height}&model=flux&nologo=true&seed={idx + 101}"
        )
        response = requests.get(image_url, timeout=(5, 20))
        content_type = response.headers.get("Content-Type", "").lower()
        if response.status_code == 200 and len(response.content) > 5000 and content_type.startswith("image/"):
            suffix = {
                "image/jpeg": ".jpg",
                "image/png": ".png",
                "image/webp": ".webp",
            }.get(content_type)
            if suffix:
                relative_path = f"media/scene_{idx}{suffix}"
                path = os.path.join("public", relative_path.replace("/", os.sep))
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "wb") as image_file:
                    image_file.write(response.content)
                return relative_path, "image"
        print(f"Flux returned no usable image for scene {idx}; trying Commons photography.")
    except (requests.RequestException, OSError, ValueError) as error:
        print(f"Flux image fallback on scene {idx}: {error}")

    try:
        return _fetch_wikimedia_photo(query, idx, orientation)
    except (requests.RequestException, ValueError, TypeError, OSError) as error:
        print(f"Wikimedia Commons photo fallback on scene {idx}: {error}")
    return "", "none"


def fetch_broll_or_ai_visual(query: str, idx: int, orientation: str):
    if os.environ.get("CINEMA_OFFLINE") == "1":
        return "", "none"

    cache = MediaAssetCache()
    cached = cache.get(query, orientation)
    if cached:
        cached_path, media_kind = cached
        relative_path = f"media/scene_{idx}_cached{cached_path.suffix}"
        destination = os.path.join("public", relative_path.replace("/", os.sep))
        os.makedirs(os.path.dirname(destination), exist_ok=True)
        shutil.copyfile(cached_path, destination)
        print(f"Reused cached {media_kind} media for scene {idx}.")
        return relative_path, media_kind

    relative_path, media_kind = _fetch_broll_or_ai_visual_uncached(
        query,
        idx,
        orientation,
    )
    if media_kind != "none" and relative_path:
        source = os.path.join("public", relative_path.replace("/", os.sep))
        cache.store(query, orientation, source, media_kind)
    return relative_path, media_kind


def _ffmpeg_executable() -> str:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        try:
            import imageio_ffmpeg

            ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        except ImportError as error:
            raise RuntimeError(
                "Install FFmpeg or imageio-ffmpeg to generate the score and transition sounds."
            ) from error
    if not ffmpeg:
        raise RuntimeError("FFmpeg is required to generate music and transition sounds.")
    return ffmpeg


def synthesize_transition_sfx(output_dir: str = "public") -> tuple[str, str]:
    os.makedirs(output_dir, exist_ok=True)
    asset_dir = os.environ.get("CINEMA_AUDIO_ASSET_DIR", "assets/audio")
    ensure_audio_assets(asset_dir)
    names = dict.fromkeys(
        name for variants in SFX_VARIANTS.values() for name in variants
    )
    for name in names:
        source = os.path.join(asset_dir, name)
        destination = os.path.join(output_dir, name)
        shutil.copyfile(source, destination)
    boom_path = os.path.join(output_dir, "sfx_boom.mp3")
    whoosh_path = os.path.join(output_dir, "sfx_whoosh.mp3")
    if any(not os.path.isfile(path) or os.path.getsize(path) == 0 for path in (boom_path, whoosh_path)):
        raise RuntimeError("Audio vault did not provide both transition sound effects.")
    return "sfx_boom.mp3", "sfx_whoosh.mp3"


def _sfx_variant_filename(scene: dict, scene_index: int) -> str:
    cue = scene.get("sfxCue")
    cue = cue if cue in SFX_VARIANTS else "whoosh"
    variants = SFX_VARIANTS[cue]
    headline = str(scene.get("headline", ""))
    digest = hashlib.sha256(headline.encode("utf-8")).digest()[0]
    return variants[(scene_index + digest) % len(variants)]


def synthesize_ambient_cinema_score(
    duration_sec: float,
    out_mp3: str,
    scenes: list,
    score_style: str = "cinema",
):
    if scenes:
        duration_sec = max(duration_sec, float(scenes[-1].get("endSec", duration_sec)))
    ffmpeg = _ffmpeg_executable()
    asset_dir = os.environ.get("CINEMA_AUDIO_ASSET_DIR", "assets/audio")
    ensure_audio_assets(asset_dir)
    bed_name = "phonk_bed.mp3" if score_style == "phonk" else "cinema_bed.mp3"
    bed_path = os.path.join(asset_dir, bed_name)
    dur = max(10.0, duration_sec + 2.0)
    fade_out_start = max(1.0, dur - 3.0)
    subprocess.run(
        [
            ffmpeg,
            "-y",
            "-stream_loop", "-1", "-i", bed_path,
            "-t", str(dur),
            "-af",
            f"afade=t=in:st=0:d=0.6,afade=t=out:st={fade_out_start}:d=3,"
            "alimiter=limit=0.9",
            "-c:a",
            "libmp3lame",
            "-b:a", "96k",
            out_mp3,
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=120,
    )
    if not os.path.isfile(out_mp3) or os.path.getsize(out_mp3) == 0:
        raise RuntimeError("FFmpeg completed without producing the ambient score.")


def analyze_beat_timestamps(audio_path: str, duration_sec: float) -> list[float]:
    try:
        import librosa

        signal, sample_rate = librosa.load(
            audio_path,
            sr=None,
            mono=True,
            duration=min(max(duration_sec, 1), 60),
        )
        beats = librosa.onset.onset_detect(
            y=signal,
            sr=sample_rate,
            units="time",
            backtrack=False,
        )
    except (ImportError, OSError, ValueError, RuntimeError) as error:
        raise RuntimeError(f"Could not analyze the generated music beats: {error}") from error
    return [
        round(float(timestamp), 3)
        for timestamp in beats
        if 0 <= float(timestamp) < duration_sec
    ][:512]


def _retime_words(words: list[dict], original_duration: float, new_duration: float) -> list[dict]:
    if original_duration <= 0 or new_duration <= 0:
        raise ValueError("Audio timing durations must be positive.")
    ratio = new_duration / original_duration
    return [
        {
            **word,
            "start": round(min(new_duration, word["start"] * ratio), 3),
            "end": round(min(new_duration, word["end"] * ratio), 3),
        }
        for word in words
    ]


def trim_voiceover_silence(path: str, words: list[dict]) -> tuple[list[dict], float]:
    original_duration = _audio_duration_seconds(path)
    edited_path = f"{path}.edited.mp3"
    auto_editor = shutil.which("auto-editor") or shutil.which("auto_editor")
    if auto_editor:
        try:
            subprocess.run(
                [
                    auto_editor, path,
                    "--edit", "audio:threshold=0.04",
                    "--margin", "0.12s",
                    "--output", edited_path,
                    "-vn", "-sn", "-dn",
                    "--audio-bitrate", "128k",
                ],
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=90,
            )
            if os.path.isfile(edited_path) and os.path.getsize(edited_path) > 0:
                new_duration = _audio_duration_seconds(edited_path)
                os.replace(edited_path, path)
                return _retime_words(words, original_duration, new_duration), new_duration
        except (OSError, subprocess.SubprocessError, RuntimeError) as error:
            detail = (
                getattr(error, "stderr", None)
                or getattr(error, "stdout", None)
                or str(error)
            )
            print(f"auto-editor silence trim failed; using FFmpeg: {detail.strip()}")
        finally:
            if os.path.exists(edited_path):
                os.remove(edited_path)

    try:
        subprocess.run(
            [
                _ffmpeg_executable(), "-y", "-i", path,
                "-af",
                "silenceremove=start_periods=1:start_duration=0.12:"
                "start_threshold=-48dB:stop_periods=1:stop_duration=0.18:"
                "stop_threshold=-48dB",
                "-c:a", "libmp3lame", "-b:a", "128k", edited_path,
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=90,
        )
        new_duration = _audio_duration_seconds(edited_path)
        os.replace(edited_path, path)
    except (OSError, subprocess.SubprocessError, RuntimeError) as error:
        if os.path.exists(edited_path):
            os.remove(edited_path)
        raise RuntimeError(f"Could not trim voiceover silence with auto-editor or FFmpeg: {error}") from error
    return _retime_words(words, original_duration, new_duration), new_duration


def mix_final_audio(
    voiceover_path: str,
    score_path: str,
    output_path: str,
    scenes: list[dict],
    duration_sec: float,
) -> None:
    asset_dir = os.environ.get("CINEMA_AUDIO_ASSET_DIR", "assets/audio")
    ensure_audio_assets(asset_dir)
    inputs = [
        _ffmpeg_executable(), "-y",
        "-i", voiceover_path,
        "-i", score_path,
    ]
    filters = [
        "[1:a]volume=0.15[bg]",
        "[bg][0:a]sidechaincompress=threshold=0.03:ratio=5:attack=18:release=280[ducked]",
        "[0:a]volume=1[voice]",
    ]
    audio_labels = ["[voice]", "[ducked]"]
    for scene_index, scene in enumerate(scenes):
        if scene.get("startSec", 0) <= 0:
            continue
        filename = _sfx_variant_filename(scene, scene_index)
        delay_ms = max(0, round(float(scene["startSec"]) * 1000))
        input_index = len(audio_labels)
        inputs.extend(["-i", os.path.join(asset_dir, filename)])
        label = f"sfx{input_index}"
        filters.append(
            f"[{input_index}:a]adelay={delay_ms}|{delay_ms},volume=0.28[{label}]"
        )
        audio_labels.append(f"[{label}]")

    filters.append(
        "".join(audio_labels)
        + f"amix=inputs={len(audio_labels)}:duration=first:normalize=0,"
        "alimiter=limit=0.95,loudnorm=I=-14:TP=-1.5:LRA=11[master]"
    )
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    subprocess.run(
        [
            *inputs,
            "-filter_complex", ";".join(filters),
            "-map", "[master]",
            "-t", str(max(1, duration_sec)),
            "-c:a", "libmp3lame",
            "-b:a", "128k",
            output_path,
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=180,
    )
    if not os.path.isfile(output_path) or os.path.getsize(output_path) == 0:
        raise RuntimeError("FFmpeg did not produce the mastered audio mix.")


def sanitize_narration(text: str) -> str:
    cleaned = html.unescape(str(text or ""))
    cleaned = re.sub(r"```[\w-]*\s*([\s\S]*?)```", r"\1", cleaned)
    cleaned = re.sub(r"!?\[([^\]]+)\]\([^)]+\)", r"\1", cleaned)
    cleaned = re.sub(r"\[[^\]]*\]|\([^)]*\)|\{[^}]*\}", " ", cleaned)
    cleaned = re.sub(r"(?m)^\s*(?:#{1,6}\s*|>\s*|[-*+]\s+)", "", cleaned)
    cleaned = re.sub(r"[*_`~#>|]", " ", cleaned)
    cleaned = "".join(
        character
        if unicodedata.category(character)[0] in {"L", "M", "N", "P", "Z"}
        else " "
        for character in cleaned
    )
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if not re.search(r"[\w\u0900-\u097f]", cleaned):
        raise ValueError("Narration contains no speakable text after sanitization.")
    return cleaned


def _audio_duration_seconds(path: str) -> float:
    ffprobe = shutil.which("ffprobe")
    if ffprobe:
        try:
            result = subprocess.run(
                [
                    ffprobe,
                    "-v",
                    "error",
                    "-show_entries",
                    "format=duration",
                    "-of",
                    "default=noprint_wrappers=1:nokey=1",
                    path,
                ],
                check=False,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                duration = float(result.stdout.strip())
                if math.isfinite(duration) and duration > 0:
                    return duration
        except (OSError, ValueError, subprocess.TimeoutExpired) as error:
            print(f"ffprobe could not read TTS duration; trying mutagen: {error}")

    try:
        from mutagen.mp3 import MP3

        duration = float(MP3(path).info.length)
    except (ImportError, OSError, ValueError) as error:
        raise RuntimeError(
            "Could not read TTS duration; install ffprobe or the mutagen dependency."
        ) from error
    if not math.isfinite(duration) or duration <= 0:
        raise RuntimeError("The generated TTS file has an invalid audio duration.")
    return duration


def _estimated_word_timings(text: str, duration: float) -> list[dict]:
    tokens = text.split()
    interval = duration / len(tokens)
    return [
        {
            "word": word,
            "start": round(index * interval, 3),
            "end": round(duration if index == len(tokens) - 1 else (index + 1) * interval, 3),
        }
        for index, word in enumerate(tokens)
    ]


def synthesize_offline_voice_and_timings(text: str, out_mp3: str) -> tuple[list[dict], float]:
    duration = max(8.0, len(text.split()) / 2.5)
    os.makedirs(os.path.dirname(out_mp3) or ".", exist_ok=True)
    subprocess.run(
        [
            _ffmpeg_executable(), "-y",
            "-f", "lavfi", "-i", "anullsrc=channel_layout=mono:sample_rate=44100",
            "-t", str(duration),
            "-c:a", "libmp3lame", "-b:a", "96k",
            out_mp3,
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return _estimated_word_timings(text, duration), duration


async def synthesize_voice_and_timings(text: str, voice: str, out_mp3: str):
    cleaned_text = sanitize_narration(text)
    if voice.startswith(("hi-IN-", "en-IN-")):
        fallback_voices = [
            "hi-IN-MadhurNeural",
            "hi-IN-SwaraNeural",
            "en-IN-PrabhatNeural",
        ]
    else:
        fallback_voices = [
            "en-US-AndrewMultilingualNeural",
            "en-US-GuyNeural",
            "en-US-ChristopherNeural",
            "en-GB-RyanNeural",
        ]
    voices = list(dict.fromkeys([voice, *fallback_voices]))
    temporary_path = f"{out_mp3}.tmp.mp3"
    os.makedirs(os.path.dirname(out_mp3) or ".", exist_ok=True)
    edge_errors = []

    for candidate_voice in voices:
        if os.path.exists(temporary_path):
            os.remove(temporary_path)
        words = []
        max_end = 0.0
        try:
            communicate = edge_tts.Communicate(
                cleaned_text,
                candidate_voice,
                rate="+0%",
                pitch="-2Hz",
                boundary="WordBoundary",
            )
            with open(temporary_path, "wb") as audio_file:
                async for chunk in communicate.stream():
                    if chunk["type"] == "audio":
                        audio_file.write(chunk["data"])
                    elif chunk["type"] == "WordBoundary":
                        start_sec = chunk["offset"] / 10_000_000.0
                        end_sec = start_sec + chunk["duration"] / 10_000_000.0
                        words.append(
                            {
                                "word": chunk["text"],
                                "start": round(start_sec, 3),
                                "end": round(end_sec, 3),
                            }
                        )
                        max_end = max(max_end, end_sec)
            if not os.path.isfile(temporary_path) or os.path.getsize(temporary_path) == 0:
                raise RuntimeError("Edge TTS returned no audio bytes.")
            if not words:
                raise RuntimeError("Edge TTS returned no word-boundary timings.")
            os.replace(temporary_path, out_mp3)
            print(f"Generated voiceover with Edge TTS ({candidate_voice}).")
            return words, max(max_end + 0.8, 6.0)
        except Exception as error:
            error_detail = str(error).strip() or type(error).__name__
            edge_errors.append(f"{candidate_voice}: {error_detail}")
            print(
                f"Edge TTS voice failed ({candidate_voice}); "
                f"trying the next voice: {error_detail}"
            )
        finally:
            if os.path.exists(temporary_path):
                os.remove(temporary_path)

    if os.path.exists(temporary_path):
        os.remove(temporary_path)
    try:
        language = "hi" if voice.startswith("hi-IN-") else "en"
        fallback_tts = gTTS(text=cleaned_text, lang=language)
        await asyncio.to_thread(fallback_tts.save, temporary_path)
        if not os.path.isfile(temporary_path) or os.path.getsize(temporary_path) == 0:
            raise RuntimeError("gTTS returned no audio bytes.")
        duration = await asyncio.to_thread(_audio_duration_seconds, temporary_path)
        os.replace(temporary_path, out_mp3)
        print(f"Generated voiceover with gTTS ({language}).")
        return _estimated_word_timings(cleaned_text, duration), duration
    except Exception as error:
        if os.path.exists(temporary_path):
            os.remove(temporary_path)
        failures = "; ".join(edge_errors)
        raise RuntimeError(
            f"All Edge TTS voices and the gTTS fallback failed. "
            f"Edge errors: {failures}. gTTS error: {error}"
        ) from error

def main():
    offline_mode = os.environ.get("CINEMA_OFFLINE") == "1"
    trending_context = ""
    if not offline_mode and re.search(r"(?<!\S)--trending(?!\S)", RAW_PROMPT, re.IGNORECASE):
        try:
            trending_context = fetch_trending_context()
        except requests.RequestException as error:
            print(f"Google Trends context unavailable; continuing without it: {error}")

    route = route_production_request(
        RAW_PROMPT,
        os.environ.get("FORMAT", "vertical"),
        research_enabled=not offline_mode,
    )
    if route.research_context:
        trending_context = "\n".join(
            part for part in (trending_context, route.research_context) if part
        )
    intent = parse_prompt_intent(
        strip_viral_flags(route.prompt),
        route.format_hint,
    )
    orientation = intent.format
    viral_plan = build_viral_plan(
        route.prompt,
        intent.mode,
        intent.duration_sec,
        trending_context=trending_context,
    )
    scene_count_instruction = "10 to 14" if viral_plan.fast_cuts else "8 to 14"

    sys_prompt = SYSTEM_PROMPT.format(
        target_words=intent.target_words,
        min_narration_words=max(60, intent.min_narration_words),
        scene_count_instruction=scene_count_instruction,
        lang_instruction=intent.lang_instruction,
        style_instruction=viral_plan.system_instruction,
        brand=intent.brand,
        color=intent.color,
        mode=intent.mode,
    )
    if route.documentary:
        sys_prompt += "\n\n" + documentary_direction(
            route.duration_sec,
            route.research_context,
        )

    prompt_context = os.environ.get("PROMPT_CONTEXT", "").strip()
    if trending_context and not route.research_context:
        prompt_context = "\n".join(
            part for part in (prompt_context, trending_context) if part
        )
    full_prompt = enhance_story_prompt(
        compose_story_prompt(intent.prompt, prompt_context),
        viral_plan,
    )
    if offline_mode:
        storyboard = build_fallback_storyboard(
            full_prompt,
            intent.brand,
            intent.color,
            intent.mode,
            intent.voice.startswith(("hi-IN-", "en-IN-")),
            min_words=intent.min_narration_words,
        )
    else:
        storyboard = generate_storyboard(
            full_prompt,
            sys_prompt,
            intent.min_narration_words,
            brand=intent.brand,
            color=intent.color,
            mode=intent.mode,
            is_hinglish=intent.voice.startswith(("hi-IN-", "en-IN-")),
        )
    narration = sanitize_narration(storyboard["narration"])

    if offline_mode:
        words, total_duration = synthesize_offline_voice_and_timings(
            narration, "public/voiceover.mp3"
        )
    else:
        words, total_duration = asyncio.run(
            synthesize_voice_and_timings(narration, intent.voice, "public/voiceover.mp3")
        )
        words, total_duration = trim_voiceover_silence(
            "public/voiceover.mp3", words
        )

    scenes = storyboard.get("scenes", [])
    total_weight = sum(s["weight"] for s in scenes)
    cursor = 0.0
    timed_scenes = []

    for idx, s in enumerate(scenes):
        dur = (
            total_duration / len(scenes)
            if viral_plan.fast_cuts
            else (s.get("weight", 1.0) / total_weight) * total_duration
        )
        s["startSec"] = round(cursor, 2)
        cursor = total_duration if idx == len(scenes) - 1 else cursor + dur
        s["endSec"] = round(cursor, 2)

        q = s["visualQuery"]
        clip_path = f"public/media/scene_{idx}.mp4"
        if (
            not offline_mode
            and idx in {0, 2}
            and try_generate_ai_video_clip(q, idx, orientation, clip_path)
        ):
            media_file, media_kind = f"media/scene_{idx}.mp4", "video"
        else:
            media_file, media_kind = fetch_broll_or_ai_visual(q, idx, orientation)
        s["mediaFile"] = media_file
        s["mediaKind"] = media_kind
        timed_scenes.append(s)

    synthesize_ambient_cinema_score(
        total_duration,
        "public/ambient_score.mp3",
        timed_scenes,
        score_style=viral_plan.score_style,
    )
    boom_file, whoosh_file = synthesize_transition_sfx("public")
    asset_dir = os.environ.get("CINEMA_AUDIO_ASSET_DIR", "assets/audio")
    beat_track = os.path.join(
        asset_dir,
        "phonk_bed.mp3" if viral_plan.score_style == "phonk" else "cinema_bed.mp3",
    )
    beat_timestamps = analyze_beat_timestamps(beat_track, total_duration)
    mix_final_audio(
        "public/voiceover.mp3",
        "public/ambient_score.mp3",
        "public/master_audio.mp3",
        timed_scenes,
        total_duration,
    )
    output = {
        "title": storyboard.get("title", "Cinema AI Video"),
        "brandTag": intent.brand,
        "themeColor": intent.color,
        "mode": intent.mode,
        "viralMode": viral_plan.archetype,
        "beatSync": viral_plan.beat_sync,
        "beatTimestamps": beat_timestamps,
        "format": intent.format,
        "totalDurationSec": round(total_duration, 2),
        "scenes": timed_scenes,
        "words": words,
        "voiceoverFile": "voiceover.mp3",
        "ambientScoreFile": "ambient_score.mp3",
        "masterAudioFile": "master_audio.mp3",
        "sfxBoomFile": boom_file,
        "sfxWhooshFile": whoosh_file,
        "sfxPopFile": "sfx_pop.mp3",
        "sfxFiles": SFX_VARIANTS,
    }
    with open("public/video_data.json", "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    print(
        f"Mastered {total_duration:.2f}s {intent.mode} film | "
        f"Scenes: {len(timed_scenes)} | Words: {len(words)}"
    )

if __name__ == "__main__":
    main()
