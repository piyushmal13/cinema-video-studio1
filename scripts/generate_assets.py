import asyncio
import json
import os
import re
import shutil
import subprocess
import time
import urllib.parse
import requests
import edge_tts
if __package__:
    from .prompt_intent import compose_story_prompt, parse_prompt_intent, validate_storyboard
else:
    from prompt_intent import compose_story_prompt, parse_prompt_intent, validate_storyboard

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
RAW_PROMPT = os.environ.get("PROMPT", "Create a cinematic short film on how AI is transforming global finance").strip()

os.makedirs("public/media", exist_ok=True)
os.makedirs("out", exist_ok=True)

SYSTEM_PROMPT = """You are an Academy-Award-caliber film director and motion-graphics creative director.
Given a user topic, story idea, or full script, craft a complete {target_words} production script and 5 to 7 distinct scenes.
{lang_instruction}
Use brandTag "{brand}", themeColor "{color}", and mode "{mode}".

Treat the user's brief as the source of truth. For a topic, create a clear beginning, explanation with useful context, concrete example, and satisfying ending. For a supplied script, preserve its key facts and intended meaning; do not replace it with a generic summary. Explain technical ideas in plain language, avoid filler, and do not invent statistics, quotations, or claims. Keep the narration complete enough for the requested runtime. Do not speak production settings or visual directions in the voiceover.
The narration MUST contain at least {min_narration_words} whitespace-separated words. This is a hard minimum, not a suggestion.

Return ONLY one valid JSON object with these top-level keys:
- "title": concise title specific to the user's brief.
- "narration": complete spoken voiceover, with no hashtags, emojis, or stage directions.
- "scenes": an array of 5 to 7 scene objects. Every object must include:
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


def generate_storyboard(prompt: str, sys_prompt: str, min_narration_words: int) -> dict:
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
                    "max_tokens": 4096,
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
                clean_json_response(raw_text), min_narration_words
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
                    f"contain at least {min_narration_words} words. Do not shorten it."
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
                        clean_json_response(raw_text), min_narration_words
                    )
                print(f"Gemini {model_id} status {resp.status_code}: {resp.text[:200]}")
            except Exception as e:
                print(f"Gemini {model_id} error: {e}")

    detail = f" Pollinations error: {pollinations_error}" if pollinations_error else ""
    if not GEMINI_API_KEY:
        raise RuntimeError(f"No valid storyboard was returned by the free provider.{detail}")
    raise RuntimeError(f"All AI providers failed to return valid JSON.{detail}")

def fetch_broll_or_ai_visual(query: str, idx: int, orientation: str):
    # Keyless Pollinations Flux image generation; the backdrop has a procedural fallback.
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
            f"Visual provider returned HTTP {r.status_code} or an undersized image "
            f"for scene {idx}; using the procedural backdrop."
        )
    except Exception as e:
        print(f"Visual fallback on scene {idx}: {e}")

    return "", "none"

def synthesize_ambient_cinema_score(duration_sec: float, out_mp3: str, scenes: list):
    dur = max(10.0, duration_sec + 2.0)
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
        raise RuntimeError("FFmpeg is required to generate the free ambient score and transition sounds.")

    inputs = [
        "-f",
        "lavfi",
        "-i",
        (
            "aevalsrc=0.18*sin(2*PI*55*t)*(0.65+0.35*sin(2*PI*0.08*t))"
            "+0.09*sin(2*PI*82.41*t)*cos(2*PI*0.06*t)"
            "+0.045*sin(2*PI*110*t)*sin(2*PI*0.04*t)"
            "+0.025*sin(2*PI*164.81*t):s=44100:d={}".format(dur)
        ),
    ]
    filters = [
        f"[0:a]lowpass=f=900,aecho=0.8:0.88:60:0.4,"
        f"afade=t=in:st=0:d=2.5,afade=t=out:st={max(1.0, dur - 3.0)}:d=3[bed]"
    ]
    mix_inputs = ["[bed]"]

    for scene in scenes[1:]:
        start = float(scene["startSec"])
        if start >= dur:
            continue
        cue = scene.get("sfxCue", "whoosh")
        input_index = len(mix_inputs)
        if cue == "boom":
            inputs.extend(["-f", "lavfi", "-i", "sine=frequency=48:duration=1.6"])
            sound_filter = "afade=t=out:st=0.2:d=1.4,lowpass=f=180"
            volume = 0.48
        elif cue == "pulse":
            inputs.extend(["-f", "lavfi", "-i", "sine=frequency=880:duration=0.45"])
            sound_filter = "afade=t=in:st=0:d=0.02,afade=t=out:st=0.08:d=0.37"
            volume = 0.22
        else:
            inputs.extend(
                [
                    "-f",
                    "lavfi",
                    "-i",
                    "anoisesrc=color=pink:sample_rate=44100:duration=1.0",
                ]
            )
            sound_filter = (
                "highpass=f=500,lowpass=f=8000,afade=t=in:st=0:d=0.12,"
                "afade=t=out:st=0.55:d=0.45"
            )
            volume = 0.24

        delay_ms = round(start * 1000)
        label = f"sfx{input_index}"
        filters.append(
            f"[{input_index}:a]{sound_filter},volume={volume},"
            f"adelay={delay_ms}:all=1[{label}]"
        )
        mix_inputs.append(f"[{label}]")

    filters.append(
        "".join(mix_inputs)
        + f"amix=inputs={len(mix_inputs)}:duration=first:normalize=0,"
        "alimiter=limit=0.95[mix]"
    )
    subprocess.run(
        [
            ffmpeg,
            "-y",
            *inputs,
            "-filter_complex",
            ";".join(filters),
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
        raise RuntimeError("FFmpeg completed without producing an ambient score.")

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
    intent = parse_prompt_intent(RAW_PROMPT, os.environ.get("FORMAT", "vertical"))
    orientation = intent.format

    sys_prompt = SYSTEM_PROMPT.format(
        target_words=intent.target_words,
        min_narration_words=intent.min_narration_words,
        lang_instruction=intent.lang_instruction,
        brand=intent.brand,
        color=intent.color,
        mode=intent.mode,
    )

    prompt_context = os.environ.get("PROMPT_CONTEXT", "").strip()
    full_prompt = compose_story_prompt(intent.prompt, prompt_context)
    storyboard = generate_storyboard(
        full_prompt, sys_prompt, intent.min_narration_words
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
        dur = (s.get("weight", 1.0) / total_weight) * total_duration
        s["startSec"] = round(cursor, 2)
        cursor += dur
        s["endSec"] = round(cursor, 2)

        q = s["visualQuery"]
        media_file, media_kind = fetch_broll_or_ai_visual(q, idx, orientation)
        s["mediaFile"] = media_file
        s["mediaKind"] = media_kind
        timed_scenes.append(s)

    synthesize_ambient_cinema_score(
        total_duration, "public/ambient_score.mp3", timed_scenes
    )
    output = {
        "title": storyboard.get("title", "Cinema AI Video"),
        "brandTag": intent.brand,
        "themeColor": intent.color,
        "mode": intent.mode,
        "format": intent.format,
        "totalDurationSec": round(total_duration, 2),
        "scenes": timed_scenes,
        "words": words,
        "voiceoverFile": "voiceover.mp3",
        "ambientScoreFile": "ambient_score.mp3",
    }
    with open("public/video_data.json", "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    print(
        f"Mastered {total_duration:.2f}s {intent.mode} film | "
        f"Scenes: {len(timed_scenes)} | Words: {len(words)}"
    )

if __name__ == "__main__":
    main()
