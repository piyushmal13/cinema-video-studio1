import asyncio
import json
import os
import re
import subprocess
import urllib.parse
import requests
import edge_tts

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "").strip()
RAW_PROMPT = os.environ.get("PROMPT", "Create a cinematic short film on how AI is transforming global finance").strip()

os.makedirs("public/media", exist_ok=True)
os.makedirs("out", exist_ok=True)

def parse_prompt_flags(prompt: str):
    voice = "en-US-AndrewMultilingualNeural"
    brand = "IFXTRADES"
    color = "#D4AF37"
    mode = "shorts"
    target_words = "95 to 125 words (approx 40-50 seconds)"
    lang_instruction = "Write the narration in dramatic, authoritative, cinematic English."

    if "--movie" in prompt.lower() or "--cinema" in prompt.lower():
        mode = "cinema"
        target_words = "160 to 230 words (approx 65-95 seconds mini-documentary / short film)"
        prompt = re.sub(r"--(movie|cinema)", "", prompt, flags=re.IGNORECASE)

    if "--hindi" in prompt.lower() or "--hinglish" in prompt.lower():
        voice = "hi-IN-MadhurNeural"
        lang_instruction = "Write the narration in dramatic, cinematic Hinglish (Hindi written cleanly in Roman script for crisp subtitles) suitable for Indian audiences."
        prompt = re.sub(r"--(hindi|hinglish)", "", prompt, flags=re.IGNORECASE)

    if "--female" in prompt.lower():
        voice = "hi-IN-SwaraNeural" if "hi-IN" in voice else "en-US-AvaMultilingualNeural"
        prompt = re.sub(r"--female", "", prompt, flags=re.IGNORECASE)

    brand_match = re.search(r"--brand=([A-Za-z0-9_ -]+)", prompt)
    if brand_match:
        brand = brand_match.group(1).strip().upper()
        prompt = prompt.replace(brand_match.group(0), "")

    color_match = re.search(r"--color=(#[0-9A-Fa-f]{6})", prompt)
    if color_match:
        color = color_match.group(1)
        prompt = prompt.replace(color_match.group(0), "")

    return prompt.strip(), voice, brand, color, mode, target_words, lang_instruction

SYSTEM_PROMPT = """You are an Academy-Award-caliber film director and motion-graphics creative director.
Given a user topic, story idea, or full script, craft a visually breathtaking {target_words} production script and 5 to 7 distinct scenes.
{lang_instruction}
Use brandTag "{brand}", themeColor "{color}", and mode "{mode}".

Return ONLY valid JSON matching this exact schema:
{{
  "title": "Cinematic Title",
  "brandTag": "{brand}",
  "themeColor": "{color}",
  "mode": "{mode}",
  "narration": "Full spoken voiceover narration with dramatic pacing and natural punctuation. No hashtags, emojis, or stage directions.",
  "scenes": [
    {{
      "type": "cinema_hero",
      "weight": 0.18,
      "kicker": "CHAPTER I • THE AWAKENING",
      "headline": "Every Empire Begins In Silence",
      "subline": "A visual journey into the next era of intelligence",
      "visualQuery": "dark futuristic city night aerial neon 4k",
      "cameraMotion": "dolly_push",
      "sfxCue": "boom"
    }},
    {{
      "type": "three_d_globe",
      "weight": 0.18,
      "kicker": "GLOBAL NETWORK",
      "headline": "Millions Of Signals Connected In Real Time",
      "visualQuery": "abstract dark technology server room blue lights",
      "cameraMotion": "zoom_in",
      "sfxCue": "whoosh"
    }},
    {{
      "type": "candlestick_chart",
      "weight": 0.18,
      "kicker": "MARKET DYNAMICS",
      "headline": "Where Liquidity Shifts, Opportunity Emerges",
      "visualQuery": "stock market trading screens dark room",
      "cameraMotion": "pan_right",
      "sfxCue": "pulse"
    }},
    {{
      "type": "three_d_bars",
      "weight": 0.16,
      "kicker": "EXPONENTIAL SCALE",
      "headline": "Autonomous Systems Outpace Manual Effort",
      "barValues": [
        {{"label": "2023", "value": 24}},
        {{"label": "2024", "value": 51}},
        {{"label": "2025", "value": 78}},
        {{"label": "2026", "value": 99}}
      ],
      "visualQuery": "luxury sports car night rain reflections",
      "cameraMotion": "zoom_out",
      "sfxCue": "whoosh"
    }},
    {{
      "type": "split_compare",
      "weight": 0.15,
      "kicker": "THE PARADIGM SHIFT",
      "headline": "Legacy Workflow vs Autonomous AI",
      "leftLabel": "Hours Of Manual Grinding",
      "rightLabel": "Instant Cloud Execution",
      "visualQuery": "minimalist dark architecture luxury interior",
      "cameraMotion": "pan_left",
      "sfxCue": "whoosh"
    }},
    {{
      "type": "cinema_outro",
      "weight": 0.15,
      "kicker": "{brand}",
      "headline": "The Future Belongs To Builders",
      "subline": "Follow for daily cinema-grade intelligence",
      "visualQuery": "sunrise over dark mountain peaks golden hour",
      "cameraMotion": "dolly_push",
      "sfxCue": "boom"
    }}
  ]
}}

Available scene types: "cinema_hero", "three_d_globe", "three_d_bars", "candlestick_chart", "split_compare", "step_list", "cinema_outro".
Rules:
1. Every scene MUST include a vivid 4-to-7 word English "visualQuery".
2. Choose "cameraMotion" from: "zoom_in", "zoom_out", "pan_left", "pan_right", "dolly_push".
3. Choose "sfxCue" from: "boom", "whoosh", "pulse".
4. Weights must sum to 1.0."""

def clean_json_response(raw_text: str) -> dict:
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw_text.strip(), flags=re.MULTILINE)
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end != -1:
        cleaned = cleaned[start : end + 1]
    return json.loads(cleaned)

def generate_storyboard(prompt: str, sys_prompt: str) -> dict:
    # 1. Primary: Google AI Studio Free Tier (current 2026 models from API error notice)
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
                    print(f"Directed with Gemini ({model_id})")
                    return clean_json_response(raw_text)
                else:
                    print(f"Gemini {model_id} status {resp.status_code}: {resp.text[:200]}")
            except Exception as e:
                print(f"Gemini {model_id} error: {e}")

    # 2. Optional: Groq Free Tier (if added later)
    if GROQ_API_KEY:
        try:
            resp = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
                json={
                    "model": "llama-3.3-70b-versatile",
                    "messages": [
                        {"role": "system", "content": sys_prompt},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.5,
                    "response_format": {"type": "json_object"},
                },
                timeout=60,
            )
            if resp.status_code == 200:
                print("Directed with Groq Llama 3.3 70B")
                return clean_json_response(resp.json()["choices"][0]["message"]["content"])
        except Exception as e:
            print(f"Groq error: {e}")

    # 3. Unlimited $0 Keyless Fallback: Pollinations OpenAI-Compatible Endpoint (zero API key, zero credits)
    for free_model in ["openai", "deepseek", "mistral"]:
        try:
            resp = requests.post(
                "https://text.pollinations.ai/openai",
                headers={"Content-Type": "application/json"},
                json={
                    "model": free_model,
                    "messages": [
                        {"role": "system", "content": sys_prompt},
                        {"role": "user", "content": f"{prompt}\n\nRespond with valid JSON only."},
                    ],
                    "temperature": 0.5,
                },
                timeout=75,
            )
            if resp.status_code == 200:
                raw_text = resp.json()["choices"][0]["message"]["content"]
                print(f"Directed with Pollinations Free ({free_model})")
                return clean_json_response(raw_text)
        except Exception as e:
            print(f"Pollinations {free_model} fallback: {e}")

    raise RuntimeError("All AI providers failed to return valid JSON.")

def fetch_broll_or_ai_visual(query: str, idx: int, orientation: str):
    # Unlimited $0 Keyless AI Cinema Still via Pollinations Flux
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
    except Exception as e:
        print(f"Visual fallback on scene {idx}: {e}")

    return "", "none"

def synthesize_ambient_cinema_score(duration_sec: float, out_mp3: str):
    dur = max(10.0, duration_sec + 2.0)
    filter_complex = (
        f"aevalsrc='0.14*sin(2*PI*55*t)*sin(2*PI*0.12*t)"
        f"+0.09*sin(2*PI*82.41*t)*cos(2*PI*0.08*t)"
        f"+0.06*sin(2*PI*110*t)*sin(2*PI*0.05*t)"
        f"+0.03*sin(2*PI*164.81*t)':s=44100:d={dur},"
        f"lowpass=f=320,aecho=0.8:0.88:60:0.4,afade=t=in:st=0:d=2.5,afade=t=out:st={max(1.0, dur-3.0)}:d=3.0"
    )
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-f", "lavfi", "-i", filter_complex, "-b:a", "128k", out_mp3],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception as e:
        print(f"Ambient score warning: {e}")

async def synthesize_voice_and_timings(text: str, voice: str, out_mp3: str):
    communicate = edge_tts.Communicate(text, voice, rate="+4%", pitch="-2Hz")
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
    return words, max(max_end + 0.8, 6.0)

def main():
    clean_prompt, voice, brand, color, mode, target_words, lang_instruction = parse_prompt_flags(RAW_PROMPT)
    orientation = "landscape" if (mode == "cinema" or os.environ.get("FORMAT") == "landscape") else "portrait"

    sys_prompt = SYSTEM_PROMPT.format(
        target_words=target_words,
        lang_instruction=lang_instruction,
        brand=brand,
        color=color,
        mode=mode,
    )

    storyboard = generate_storyboard(clean_prompt, sys_prompt)
    narration = re.sub(r"\s+", " ", storyboard["narration"]).strip()

    words, total_duration = asyncio.run(synthesize_voice_and_timings(narration, voice, "public/voiceover.mp3"))
    synthesize_ambient_cinema_score(total_duration, "public/ambient_score.mp3")

    scenes = storyboard.get("scenes", [])
    total_weight = sum(s.get("weight", 1.0) for s in scenes) or 1.0
    cursor = 0.0
    timed_scenes = []

    for idx, s in enumerate(scenes):
        dur = (s.get("weight", 1.0) / total_weight) * total_duration
        s["startSec"] = round(cursor, 2)
        cursor += dur
        s["endSec"] = round(cursor, 2)

        q = s.get("visualQuery", clean_prompt)
        media_file, media_kind = fetch_broll_or_ai_visual(q, idx, orientation)
        s["mediaFile"] = media_file
        s["mediaKind"] = media_kind
        timed_scenes.append(s)

    output = {
        "title": storyboard.get("title", "Cinema AI Video"),
        "brandTag": storyboard.get("brandTag", brand),
        "themeColor": storyboard.get("themeColor", color),
        "mode": mode,
        "totalDurationSec": round(total_duration, 2),
        "scenes": timed_scenes,
        "words": words,
    }
    with open("public/video_data.json", "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    print(f"Mastered {total_duration:.2f}s {mode} film | Scenes: {len(timed_scenes)} | Words: {len(words)}")

if __name__ == "__main__":
    main()
