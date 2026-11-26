import asyncio
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.parse
import requests
import edge_tts
if __package__:
    from .prompt_intent import compose_story_prompt, parse_prompt_intent, validate_storyboard
    from .viral_engineer import (
        build_viral_plan,
        enhance_story_prompt,
        fetch_trending_context,
        strip_viral_flags,
    )
else:
    from prompt_intent import compose_story_prompt, parse_prompt_intent, validate_storyboard
    from viral_engineer import (
        build_viral_plan,
        enhance_story_prompt,
        fetch_trending_context,
        strip_viral_flags,
    )

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


def generate_storyboard(
    prompt: str,
    sys_prompt: str,
    min_narration_words: int,
    scene_count_range: tuple[int, int] = (5, 7),
) -> dict:
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
                min_narration_words,
                scene_count_range=scene_count_range,
            )
            print(f"Directed with Pollinations Free ({free_model})")
            return storyboard
        except (IndexError, KeyError, TypeError, ValueError) as e:
            pollinations_error = str(e)
            print(f"Pollinations {free_model} response rejected: {e}")
            if attempt == 0:
                scene_requirement = (
                    f"exactly {scene_count_range[0]}"
                    if scene_count_range[0] == scene_count_range[1]
                    else f"{scene_count_range[0]} to {scene_count_range[1]}"
                )
                retry_prompt = (
                    f"{prompt}\n\nThe previous response was rejected: {e}. "
                    f"Return a complete corrected JSON object. The narration must "
                    f"contain at least {min_narration_words} words. Include "
                    f"{scene_requirement} scenes. Do not shorten it."
                )
                time.sleep(46)

    if GEMINI_API_KEY:
        for model_id in ["gemini-3.8-flash", "gemini-3.5-flash-lite", "gemini-3-flash-preview"]:
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_id}:generateContent?key={GEMINI_API_KEY}"
                resp = requests.post(
                    url,
                    headers={"Content-Type": "application/json"},
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
                        min_narration_words,
                        scene_count_range=scene_count_range,
                    )
                print(f"Gemini {model_id} status {resp.status_code}: {resp.text[:200]}")
            except Exception as e:
                print(f"Gemini {model_id} error: {e}")

    detail = f" Pollinations error: {pollinations_error}" if pollinations_error else ""
    if not GEMINI_API_KEY:
        raise RuntimeError(f"No valid storyboard was returned by the free provider.{detail}")
    raise RuntimeError(f"All AI providers failed to return valid JSON.{detail}")


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


def fetch_broll_or_ai_visual(query: str, idx: int, orientation: str):
    # Prefer keyless Flux stills, then use Wikimedia Commons public-domain/CC0 photography.
    try:
        w, h = (1280, 720) if orientation == "landscape" else (768, 1344)
        styled_prompt = urllib.parse.quote(
            f"{query}, dark moody cinematic film still, anamorphic lens flare, 8k photorealistic, obsidian and gold lighting"
        )
        img_url = f"https://image.pollinations.ai/prompt/{styled_prompt}?width={w}&height={h}&model=flux&nologo=true&seed={idx+101}"
        r = requests.get(img_url, timeout=40)
        if r.status_code == 200 and len(r.content) > 5000:
            out_path = f"public/media/scene_{idx}.jpg"
            with open(out_path, "wb") as f:
                f.write(r.content)
            return f"media/scene_{idx}.jpg", "image"
        print(
            f"Flux image provider returned HTTP {r.status_code} or an undersized image "
            f"for scene {idx}; trying Wikimedia Commons."
        )
    except Exception as e:
        print(f"Flux image fallback on scene {idx}: {e}")

    try:
        response = requests.get(
            "https://commons.wikimedia.org/w/api.php",
            params={
                "action": "query",
                "generator": "search",
                "gsrsearch": f"filetype:bitmap {query}",
                "gsrnamespace": 6,
                "gsrlimit": 6,
                "prop": "imageinfo",
                "iiprop": "url|extmetadata",
                "iiurlwidth": 1280 if orientation == "landscape" else 768,
                "format": "json",
            },
            headers={"User-Agent": "CinemaVideoStudio/3.0 (Wikimedia Commons media search)"},
            timeout=10,
        )
        response.raise_for_status()
        pages = response.json().get("query", {}).get("pages", {})
        for page in pages.values():
            image_info = (page.get("imageinfo") or [{}])[0]
            license_meta = image_info.get("extmetadata", {}).get("LicenseShortName", {})
            license_name = re.sub(
                r"<[^>]+>", "", str(license_meta.get("value", ""))
            ).strip().lower()
            if license_name not in {"cc0", "public domain"}:
                continue
            image_url = image_info.get("thumburl") or image_info.get("url")
            if not image_url:
                continue
            image_response = requests.get(
                image_url,
                headers={"User-Agent": "CinemaVideoStudio/3.0"},
                timeout=10,
            )
            image_response.raise_for_status()
            if (
                len(image_response.content) <= 5000
                or "image/jpeg" not in image_response.headers.get("Content-Type", "").lower()
            ):
                continue
            path = f"public/media/scene_{idx}_photo.jpg"
            with open(path, "wb") as image_file:
                image_file.write(image_response.content)
            print(
                f"Using Wikimedia Commons {license_name} photo for scene {idx}: "
                f"{page.get('title', 'untitled')}"
            )
            return f"media/scene_{idx}_photo.jpg", "image"
    except (requests.RequestException, ValueError, OSError) as error:
        print(f"Wikimedia Commons fallback on scene {idx}: {error}")

    return "", "none"


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
    ffmpeg = _ffmpeg_executable()
    os.makedirs(output_dir, exist_ok=True)
    boom_path = os.path.join(output_dir, "sfx_boom.mp3")
    whoosh_path = os.path.join(output_dir, "sfx_whoosh.mp3")
    commands = [
        [
            ffmpeg,
            "-y",
            "-f",
            "lavfi",
            "-i",
            "aevalsrc=0.85*sin(2*PI*(48+80*exp(-7*t))*t)*exp(-2.8*t):s=44100:d=1.6",
            "-af",
            "lowpass=f=180,alimiter=limit=0.95",
            "-c:a",
            "libmp3lame",
            "-b:a",
            "160k",
            boom_path,
        ],
        [
            ffmpeg,
            "-y",
            "-f",
            "lavfi",
            "-i",
            "anoisesrc=color=pink:sample_rate=44100:duration=0.8",
            "-af",
            "highpass=f=220,lowpass=f=11000,afade=t=in:st=0:d=0.05,"
            "afade=t=out:st=0.45:d=0.35,alimiter=limit=0.95",
            "-c:a",
            "libmp3lame",
            "-b:a",
            "160k",
            whoosh_path,
        ],
    ]
    for command in commands:
        subprocess.run(command, check=True, capture_output=True, text=True, timeout=30)
    if any(not os.path.isfile(path) or os.path.getsize(path) == 0 for path in (boom_path, whoosh_path)):
        raise RuntimeError("FFmpeg completed without producing both transition sound effects.")
    return "sfx_boom.mp3", "sfx_whoosh.mp3"


def synthesize_ambient_cinema_score(
    duration_sec: float,
    out_mp3: str,
    scenes: list,
    score_style: str = "cinema",
):
    dur = max(10.0, duration_sec + 2.0)
    ffmpeg = _ffmpeg_executable()
    fade_out_start = max(1.0, dur - 3.0)
    if score_style == "phonk":
        inputs = [
            "-f",
            "lavfi",
            "-i",
            (
                f"aevalsrc=0.34*sin(2*PI*55*t)"
                f"*abs(cos(2*PI*2*t))*abs(cos(2*PI*2*t))"
                f"*abs(cos(2*PI*2*t))*abs(cos(2*PI*2*t)):s=44100:d={dur}"
            ),
            "-f",
            "lavfi",
            "-i",
            (
                f"aevalsrc=0.14*(sin(2*PI*880*t)+0.45*sin(2*PI*1320*t))"
                f"*abs(cos(2*PI*2*t))*abs(cos(2*PI*2*t))"
                f"*abs(cos(2*PI*2*t))*abs(cos(2*PI*2*t)):s=44100:d={dur}"
            ),
            "-f",
            "lavfi",
            "-i",
            (
                f"aevalsrc=0.065*sin(2*PI*9000*t)"
                f"*abs(cos(2*PI*4*t))*abs(cos(2*PI*4*t))"
                f"*abs(cos(2*PI*4*t))*abs(cos(2*PI*4*t)):s=44100:d={dur}"
            ),
        ]
        filters = (
            "[0:a]volume=0.75[808];"
            "[1:a]volume=0.85[cowbell];"
            "[2:a]volume=0.5[hat];"
            "[808][cowbell][hat]amix=inputs=3:duration=first:normalize=0,"
            "lowpass=f=12000,aecho=0.55:0.7:45:0.25,"
            f"afade=t=in:st=0:d=0.25,afade=t=out:st={fade_out_start}:d=3,"
            "alimiter=limit=0.85[mix]"
        )
    else:
        inputs = [
            "-f",
            "lavfi",
            "-i",
            (
                f"aevalsrc=0.20*sin(2*PI*55*t)*(0.65+0.35*sin(2*PI*0.08*t))"
                f"+0.10*sin(2*PI*82.41*t)*cos(2*PI*0.06*t)"
                f"+0.05*sin(2*PI*110*t)*sin(2*PI*0.04*t)"
                f"+0.035*sin(2*PI*164.81*t):s=44100:d={dur}"
            ),
        ]
        filters = (
            "[0:a]lowpass=f=900,aecho=0.8:0.88:60:0.4,"
            f"afade=t=in:st=0:d=2.5,afade=t=out:st={fade_out_start}:d=3,"
            "alimiter=limit=0.85[mix]"
        )
    subprocess.run(
        [
            ffmpeg,
            "-y",
            *inputs,
            "-filter_complex",
            filters,
            "-map",
            "[mix]",
            "-c:a",
            "libmp3lame",
            "-b:a",
            "192k",
            out_mp3,
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    if not os.path.isfile(out_mp3) or os.path.getsize(out_mp3) == 0:
        raise RuntimeError("FFmpeg completed without producing the ambient score.")

async def synthesize_voice_and_timings(text: str, voice: str, out_mp3: str):
    communicate = edge_tts.Communicate(
        text,
        voice,
        rate="+0%",
        pitch="-2Hz",
        boundary="WordBoundary",
    )
    words = []
    max_end = 0.0
    with open(out_mp3, "wb") as f:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                start_sec = chunk["offset"] / 10_000_000.0
                dur_sec = chunk["duration"] / 10_000_000.0
                end_sec = start_sec + dur_sec
                words.append({
                    "word": chunk["text"],
                    "start": round(start_sec, 3),
                    "end": round(end_sec, 3),
                })
                if end_sec > max_end:
                    max_end = end_sec
    if not os.path.isfile(out_mp3) or os.path.getsize(out_mp3) == 0:
        raise RuntimeError("Text-to-speech returned no audio.")
    if not words:
        raise RuntimeError("Text-to-speech returned no word timings for captions.")
    return words, max(max_end + 0.8, 6.0)

def main():
    trending_context = ""
    if re.search(r"(?<!\S)--trending(?!\S)", RAW_PROMPT, re.IGNORECASE):
        try:
            trending_context = fetch_trending_context()
        except requests.RequestException as error:
            print(f"Google Trends context unavailable; continuing without it: {error}")

    intent = parse_prompt_intent(
        strip_viral_flags(RAW_PROMPT),
        os.environ.get("FORMAT", "vertical"),
    )
    orientation = intent.format
    viral_plan = build_viral_plan(
        RAW_PROMPT,
        intent.mode,
        intent.duration_sec,
        trending_context=trending_context,
    )
    scene_count_range = (
        (viral_plan.scene_count, viral_plan.scene_count)
        if viral_plan.fast_cuts
        else (5, 7)
    )
    scene_count_instruction = (
        f"exactly {scene_count_range[0]}"
        if scene_count_range[0] == scene_count_range[1]
        else f"{scene_count_range[0]} to {scene_count_range[1]}"
    )

    sys_prompt = SYSTEM_PROMPT.format(
        target_words=intent.target_words,
        min_narration_words=intent.min_narration_words,
        scene_count_instruction=scene_count_instruction,
        lang_instruction=intent.lang_instruction,
        style_instruction=viral_plan.system_instruction,
        brand=intent.brand,
        color=intent.color,
        mode=intent.mode,
    )

    prompt_context = os.environ.get("PROMPT_CONTEXT", "").strip()
    full_prompt = enhance_story_prompt(
        compose_story_prompt(intent.prompt, prompt_context),
        viral_plan,
    )
    storyboard = generate_storyboard(
        full_prompt,
        sys_prompt,
        intent.min_narration_words,
        scene_count_range=scene_count_range,
    )
    narration = re.sub(r"\s+", " ", storyboard["narration"]).strip()

    words, total_duration = asyncio.run(
        synthesize_voice_and_timings(narration, intent.voice, "public/voiceover.mp3")
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
        if idx in {0, 2} and try_generate_ai_video_clip(q, idx, orientation, clip_path):
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
    output = {
        "title": storyboard.get("title", "Cinema AI Video"),
        "brandTag": intent.brand,
        "themeColor": intent.color,
        "mode": intent.mode,
        "viralMode": viral_plan.archetype,
        "beatSync": viral_plan.beat_sync,
        "format": intent.format,
        "totalDurationSec": round(total_duration, 2),
        "scenes": timed_scenes,
        "words": words,
        "voiceoverFile": "voiceover.mp3",
        "ambientScoreFile": "ambient_score.mp3",
        "sfxBoomFile": boom_file,
        "sfxWhooshFile": whoosh_file,
    }
    with open("public/video_data.json", "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    print(
        f"Mastered {total_duration:.2f}s {intent.mode} film | "
        f"Scenes: {len(timed_scenes)} | Words: {len(words)}"
    )

if __name__ == "__main__":
    main()
