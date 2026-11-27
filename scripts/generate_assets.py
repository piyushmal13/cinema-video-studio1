import asyncio
import hashlib
import html
import json
import math
import os
import random
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
    from .creative_director import (
        build_creative_direction,
        choose_video_scene_indexes,
        classify_topic,
        diversify_scenes,
        stable_visual_seed,
    )
    from .visual_director import assign_visual_language
    from .comfyui_client import generate_from_environment
    from .speech_alignment import align_with_whisperx
    from .timeline_export import export_otio
    from .visual_quality import audit_visual_plan
    from .kokoro_tts import generate_from_environment as generate_kokoro_from_environment
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
    from creative_director import (
        build_creative_direction,
        choose_video_scene_indexes,
        classify_topic,
        diversify_scenes,
        stable_visual_seed,
    )
    from visual_director import assign_visual_language
    from comfyui_client import generate_from_environment
    from speech_alignment import align_with_whisperx
    from timeline_export import export_otio
    from visual_quality import audit_visual_plan
    from kokoro_tts import generate_from_environment as generate_kokoro_from_environment

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
RAW_PROMPT = os.environ.get("PROMPT", "Create a cinematic short film on how AI is transforming global finance").strip()
JOB_ID = os.environ.get("CINEMA_JOB_ID", "").strip() or str(time.time_ns())
SCENE_MEDIA_FILES: dict[int, list[str]] = {}

os.makedirs("public/media", exist_ok=True)
os.makedirs("out", exist_ok=True)

SYSTEM_PROMPT = """You are the creative director and lead writer of a professional, subject-led video studio.
Create a complete {target_words} spoken script and {scene_count_instruction} purposeful scenes.
{lang_instruction}
{style_instruction}
{creative_direction}
Use brandTag "{brand}", themeColor "{color}", and mode "{mode}".

BRIEF MODE: The user has supplied an idea or instruction, not a finished script. Understand the real request, research it when requested/current, and write original narration. Never copy the Telegram command into voiceover.
SCRIPT MODE: When the user supplied a complete script, keep that exact script as the spoken narration. Do not paraphrase, summarise, shorten, translate or insert additional spoken words. Direct scenes and timing around it.
Do not invent facts, prices, statistics, quotes, people, sources or outcomes. Distinguish verified facts, analysis and scenarios. Never invent market data. Never use a chart without supplied or retrieved values. No generic AI phrases, empty hype, filler, or repetitive conclusions.
Never add a brand, logo, watermark, CTA or product promotion unless explicitly requested.

Return ONLY one valid JSON object:
- title: specific, concise title
- narration: complete spoken narration
- scenes: {scene_count_instruction} scenes. Each scene must include type, weight, kicker, headline,
  visualQuery (4–7 specific words), cameraMotion, sfxCue and visualTreatment.
- Optional: subline, statValue, bullets (up to 4), leftLabel, rightLabel, barValues (source-backed only),
  mediaMode ("video", "image", or "graphic"), shotSize.
- visualTreatment must be one of hero_full_bleed, documentary_lower_third, editorial_split,
  editorial_cover, kinetic_typography, vertical_timeline, process_blueprint, comparative_split,
  data_stage, market_chart, orbit_stage, cinema_end_frame, immersive_photo, photo_essay,
  cinematic_side_caption. The director may refine the composition to enforce film-wide variety.

Available scene types: cinema_hero, three_d_globe, three_d_bars, candlestick_chart, split_compare, step_list, cinema_outro, kinetic_type, process_diagram, editorial_montage, data_viz.
Use a different purposeful visual subject and shot family for every scene. Consecutive scenes must not repeat the same visual query, composition or treatment.
cameraMotion: zoom_in, zoom_out, pan_left, pan_right, dolly_push, tilt_up, tilt_down,
drift_diagonal, handheld, static.
sfxCue: boom, whoosh, riser, pulse.
Weights must be positive. Data must be grounded. Illustrative visuals must be clearly labelled illustrative.
Narration minimum for brief mode: {min_narration_words} words. In script mode, the supplied script overrides this length target."""


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
    """Topic-aware degraded storyboard; never repeats a fixed sample film."""
    latest_request = re.search(
        r"Latest request:\s*(.*?)(?:\n\n|$)", prompt, re.IGNORECASE | re.DOTALL
    )
    brief = latest_request.group(1) if latest_request else prompt
    brief = re.sub(r"\s+", " ", brief).strip()
    ignored = {
        "a", "an", "and", "the", "for", "to", "of", "in", "on", "with", "about",
        "make", "create", "build", "generate", "produce", "video", "reel", "film",
        "short", "vertical", "landscape", "aaj", "abhi", "pane", "hisab", "se",
        "pura", "accha", "achha", "banao", "bana", "kar", "karo", "please",
    }
    topic_tokens = [
        word for word in re.findall(r"[\w'-]+", brief, flags=re.UNICODE)
        if word.casefold() not in ignored and len(word) > 1
    ]
    topic = " ".join(topic_tokens[:5]) or "the requested subject"
    kind = classify_topic(brief)
    rng = random.Random(stable_visual_seed(JOB_ID, 0, brief))

    if kind == "market_update":
        if is_hinglish:
            blocks = [
                f"Aaj ka market brief {topic} par focused hai. Sabse pehle timestamp aur source ke saath available data dekhein.",
                "Gold futures, dollar index aur Treasury yields alag instruments hain. Futures quote ko XAUUSD spot mat samjhein.",
                "Headline ko market move se tabhi connect karein jab source aur timing dono us explanation ko support karein.",
                "Current session ke catalysts aur upcoming economic calendar events ko clearly alag rakhein.",
                "Bullish aur bearish scenarios conditional possibilities hain, guaranteed direction ya trade calls nahi.",
                "Agar verified live quote available nahi hai, exact level banane ke bajaye limitation ko openly batayein.",
            ]
            extensions = [
                "Intraday move ko previous close, active session aur available liquidity ke context mein samajhna zaroori hai.",
                "USD aur yields ka direction useful context de sakta hai, lekin ek indicator akela cause prove nahi karta.",
                "Economic release ke actual result ko consensus aur previous reading se compare karna chahiye.",
                "Volatility ke time spread aur execution risk badal sakta hai, isliye chart ke saath conditions bhi dekhein.",
                "News headline aur market reaction ke beech timing mismatch ho toh causal claim avoid karein.",
                "Next update tabhi meaningful hoga jab naya data ya confirmed event market context ko badle.",
            ]
        else:
            blocks = [
                f"This market briefing focuses on {topic}. Start with only the price and event data that has a timestamp and identifiable source.",
                "Gold futures, the dollar index and Treasury yields are different instruments. A futures quote must never be labelled as XAUUSD spot.",
                "Connect a headline to a market move only when its source and timing support that explanation.",
                "Separate the current session's catalysts from events that are still ahead on the economic calendar.",
                "Bullish and bearish scenarios are conditional possibilities, not guaranteed direction or trading instructions.",
                "When a verified live quote is unavailable, disclose the gap rather than inventing a price level.",
            ]
            extensions = [
                "Compare the intraday move with the previous close, active session and available liquidity before drawing a conclusion.",
                "Dollar and yield direction can provide useful context, but one indicator alone does not prove causation.",
                "Compare an economic release with both consensus and its previous reading before explaining the surprise.",
                "Volatility can change spreads and execution conditions, so market structure matters alongside the chart.",
                "Avoid causal claims when a headline and the observed price reaction do not line up in time.",
                "The next update matters when fresh evidence or a confirmed event changes the market context.",
            ]
        specs = [
            ("cinema_hero", "MARKET OPEN", "The move that matters", "gold trading floor opening session", "dolly_push", "boom"),
            ("editorial_montage", "PRICE CONTEXT", "Read the verified snapshot", "gold bullion macro newsroom closeup", "pan_left", "whoosh"),
            ("data_viz", "CROSS ASSET", "Connect the market drivers", "dollar index treasury yields terminal", "zoom_in", "pulse"),
            ("process_diagram", "CATALYSTS", "What changed the session", "economic calendar analyst desk release", "pan_right", "whoosh"),
            ("split_compare", "SCENARIOS", "Separate fact from outlook", "bullish bearish scenario analysis desk", "zoom_out", "pulse"),
            ("cinema_outro", "TAKEAWAY", "What deserves attention next", "financial district market close view", "dolly_push", "boom"),
        ]
    elif kind == "commercial":
        if is_hinglish:
            blocks = [
                f"Yeh production {topic} ko ek real customer need ke through introduce karti hai, generic slogan ke through nahi.",
                "Product dikhane se pehle viewer ki actual situation aur problem establish karein.",
                "Ek real feature ko product detail, interface ya physical action se demonstrate karein.",
                "Differentiator wahi batayein jo supplied product information support karti hai.",
                "Ending mein requested next step dein; fake testimonial ya guarantee mat banayein.",
            ]
            extensions = [
                "Abstract animation se zyada useful actual product ka clear close-up demonstration hota hai.",
                "Feature ko us environment mein dikhayein jahan target customer use karega.",
                "Pricing aur performance claims ko source brief ke saath exactly match karein.",
                "Visual sequence benefit prove kare, same claim ko captions mein repeat na karein.",
                "CTA tabhi use karein jab user ne request kiya ho ya destination diya ho.",
                "Strong ending viewer ko ek clear next action deti hai.",
            ]
        else:
            blocks = [
                f"This production introduces {topic} through a specific audience need instead of a generic product slogan.",
                "Show the customer's situation before introducing the product or service.",
                "Demonstrate one real feature through a product detail, interface or physical action.",
                "Explain the differentiator only when it is supported by supplied product information.",
                "Close with the requested next step without inventing testimonials, outcomes or guarantees.",
            ]
            extensions = [
                "A close-up demonstration is more useful than an abstract animation that never shows the actual product.",
                "Show the feature in the environment where the intended audience would use it.",
                "Keep any pricing, performance or compatibility detail aligned with the supplied source.",
                "Let the visual sequence prove the benefit instead of repeating the claim in several captions.",
                "Use a clear call to action only when the user has requested one or supplied the destination.",
                "The strongest ending leaves the audience with one understandable next action.",
            ]
        specs = [
            ("cinema_hero", "THE NEED", "Start with the real problem", "customer product use environment closeup", "dolly_push", "boom"),
            ("editorial_montage", "THE PRODUCT", "Show the product in context", "authentic product surface macro detail", "pan_left", "whoosh"),
            ("process_diagram", "THE DEMO", "Make the feature tangible", "real product interface interaction recording", "zoom_in", "pulse"),
            ("split_compare", "THE DIFFERENCE", "Show the meaningful distinction", "before after product workflow comparison", "pan_right", "whoosh"),
            ("cinema_outro", "NEXT STEP", "Close with a clear action", "product hero natural studio detail", "zoom_out", "boom"),
        ]
    elif kind in {"technology", "explainer"}:
        if is_hinglish:
            blocks = [
                f"Yeh film {topic} ke peeche ka real problem ya question identify karti hai.",
                "Process ko chalane wale physical ya digital components ko clearly dikhayein.",
                "Information, materials ya decisions system mein kis order se move karte hain, samjhayen.",
                "Ek practical example ke saath un limitations ko batayein jo result badal sakti hain.",
                "Ending mein viewer ke liye iska real-world meaning clear karein.",
            ]
            extensions = [
                "Decorative shapes se better hai actual interface ya physical demonstration dikhana.",
                "Technical terms ko usi waqt explain karein jab viewer ko unki zaroorat ho.",
                "System kya karne ke liye bana hai aur practically kya kar sakta hai, dono alag rakhein.",
                "Input, process aur output dikhayein taaki cause aur effect clear ho.",
                "Jahan method fail ho sakta hai, wahan ek counterexample use karein.",
                "Final takeaway opening mein uthaye gaye question ka jawab de.",
            ]
        else:
            blocks = [
                f"This film investigates {topic} by identifying the real problem or question behind it.",
                "Show the physical or digital components that make the process work.",
                "Explain how information, materials or decisions move through the system in order.",
                "Use one concrete example and identify the limitations that change the result.",
                "Finish with the practical consequence for someone using or learning the technology.",
            ]
            extensions = [
                "A real interface or physical demonstration is more useful than a decorative floating diagram.",
                "Define unfamiliar terms at the moment they become necessary, not in a long opening lecture.",
                "Separate what the system is designed to do from what it can reliably do in practice.",
                "Show the input, the process and the output so the viewer can follow cause and effect.",
                "Include a counterexample when it helps explain where the method stops working.",
                "The final takeaway should answer the question raised in the opening scene.",
            ]
        specs = [
            ("cinema_hero", "THE QUESTION", "What does it actually do", "real hardware lab environment", "dolly_push", "boom"),
            ("editorial_montage", "THE COMPONENTS", "Look inside the system", "macro circuit board hands assembly", "pan_left", "whoosh"),
            ("process_diagram", "THE MECHANISM", "Follow the information flow", "technical process schematic sequence", "zoom_in", "pulse"),
            ("data_viz", "THE EVIDENCE", "Measure what can be measured", "software interface actual metrics display", "pan_right", "whoosh"),
            ("split_compare", "THE LIMITS", "Understand the tradeoffs", "technology use case comparison scene", "zoom_out", "pulse"),
            ("cinema_outro", "THE IMPACT", "Why this changes the workflow", "human using technology environment", "dolly_push", "boom"),
        ]
    else:
        if is_hinglish:
            blocks = [
                f"{topic} ko samajhne ke liye pehle ek real question se shuru karein, generic introduction se nahi.",
                f"Ek specific example dikhayein jo {topic} ko turant understandable banaye.",
                "Important mechanism ya sequence ko natural order mein explain karein.",
                "Ek counterpoint ya detail dikhayein jo viewer ka perspective badalti hai.",
                "Ending mein ek practical takeaway dein jo explanation se logically nikalta hai.",
            ]
            extensions = [
                "Viewer ko utna context dein jitna samajhne ke liye zaroori hai.",
                "Main idea ko visible banane ke liye real object, action ya situation use karein.",
                "Apni interpretation ko verified facts se clearly alag rakhein.",
                "Ek useful counterpoint explanation ko zyada credible banata hai.",
                "Reliable source ke bina statistics ya quotations add na karein.",
                "Conclusion mein naya meaning dein, opening line ko repeat na karein.",
            ]
        else:
            blocks = [
                f"Start with the most interesting real question about {topic}, not a generic introduction.",
                f"Show a specific example or scene that makes {topic} immediately understandable.",
                "Explain the important mechanism or sequence in a natural order.",
                "Introduce a counterpoint or detail that changes how the viewer sees the subject.",
                "End with one practical takeaway that follows from the explanation.",
            ]
            extensions = [
                "Give the viewer enough context to understand why this moment or detail matters.",
                "Use a concrete object, action or situation to make the main idea visible.",
                "Keep interpretation separate from details that can actually be verified.",
                "A useful counterpoint makes the explanation more credible and less predictable.",
                "Avoid adding statistics or quotations unless a reliable source supplied them.",
                "The conclusion should add meaning rather than repeat the opening sentence.",
            ]
        specs = [
            ("cinema_hero", "THE HOOK", "Open on a specific moment", "subject documentary establishing scene", "dolly_push", "boom"),
            ("editorial_montage", "THE DETAIL", "Show the evidence up close", "authentic macro detail photography", "pan_left", "whoosh"),
            ("process_diagram", "THE MECHANISM", "Make the process visible", "topic process demonstration sequence", "zoom_in", "pulse"),
            ("data_viz", "THE CONTEXT", "Add useful supporting context", "relevant real world information display", "pan_right", "whoosh"),
            ("split_compare", "THE COUNTERPOINT", "Show what changes the view", "contrasting real world situation", "zoom_out", "pulse"),
            ("cinema_outro", "THE TAKEAWAY", "Finish on the practical meaning", "subject relevant human environment", "dolly_push", "boom"),
        ]

    narration_parts = list(blocks)
    for extension in extensions:
        if len(" ".join(narration_parts).split()) >= max(35, min_words):
            break
        narration_parts.append(extension)
    narration = " ".join(narration_parts)

    topic_subject = topic.split()[:2]
    middle_specs = list(specs[1:-1])
    rng.shuffle(middle_specs)
    specs = specs[:1] + middle_specs + specs[-1:]
    scenes = []
    for index, (scene_type, kicker, headline, visual_hint, motion, cue) in enumerate(specs):
        query_words = topic_subject + visual_hint.split()[:5]
        visual_query = " ".join(query_words[:7])
        if len(visual_query.split()) < 4:
            visual_query = " ".join((visual_query + " documentary footage closeup wide").split()[:7])
        scenes.append({
            "type": scene_type,
            "weight": 1.0,
            "kicker": kicker,
            "headline": headline,
            "subline": topic if index in {0, len(specs) - 1} else "",
            "visualQuery": visual_query,
            "cameraMotion": motion,
            "sfxCue": cue,
            "mediaMode": "video" if index in {0, len(specs) - 1} else "image",
        })
    return {
        "title": f"{topic.title()} | Studio Production",
        "brandTag": brand,
        "themeColor": color,
        "mode": mode,
        "narration": narration,
        "scenes": scenes,
        "degradedMode": True,
    }



def generate_storyboard(
    prompt: str,
    sys_prompt: str,
    min_narration_words: int,
    brand: str = "",
    color: str = "#A8B2C0",
    mode: str = "shorts",
    is_hinglish: bool = False,
    variation_key: str = "",
    script_mode: bool = False,
) -> dict:
    minimum_words = max(1 if script_mode else 60, min_narration_words)
    variation_key = variation_key or JOB_ID
    variation_instruction = (
        f"\n\nCreative variation key: {variation_key}. This is a new production. "
        "Choose a fresh narrative angle, examples, shot sequence and visual treatment. "
        "Do not reuse a generic template or mention this key."
    )
    user_prompt = f"{prompt}{variation_instruction}"

    # 1) Optional self-hosted Ollama brain (works in Colab or on a reachable private server).
    ollama_base = os.environ.get("OLLAMA_BASE_URL", "").strip().rstrip("/")
    if ollama_base:
        model = os.environ.get("OLLAMA_MODEL", "gemma4:26b")
        try:
            response = requests.post(
                f"{ollama_base}/api/chat",
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": sys_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "format": "json",
                    "stream": False,
                    "options": {"temperature": 0.88},
                },
                timeout=120,
            )
            response.raise_for_status()
            raw = response.json().get("message", {}).get("content", "")
            result = validate_storyboard(clean_json_response(raw), minimum_words)
            result["storyboardProvider"] = f"ollama:{model}"
            print(f"Creative director used self-hosted Ollama ({model}).")
            return result
        except Exception as error:
            print(f"Ollama director unavailable; trying Gemini/Pollinations: {error}")

    # 2) Prefer the configured Gemini API over the keyless generic provider.
    if GEMINI_API_KEY and os.environ.get("PREFER_GEMINI", "1").casefold() not in {"0", "false", "no"}:
        models = list(dict.fromkeys([
            os.environ.get("GEMINI_MODEL", "gemini-3.8-flash"),
            "gemini-3.5-flash-lite",
            "gemini-3.6-flash",
        ]))
        for model_id in models:
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_id}:generateContent"
                response = requests.post(
                    url,
                    headers={
                        "Content-Type": "application/json",
                        "x-goog-api-key": GEMINI_API_KEY,
                    },
                    json={
                        "systemInstruction": {"parts": [{"text": sys_prompt}]},
                        "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
                        "generationConfig": {
                            "responseMimeType": "application/json",
                            "maxOutputTokens": 8192,
                        },
                    },
                    timeout=75,
                )
                if response.status_code != 200:
                    print(f"Gemini {model_id} returned HTTP {response.status_code}: {response.text[:180]}")
                    continue
                raw = response.json()["candidates"][0]["content"]["parts"][0]["text"]
                result = validate_storyboard(clean_json_response(raw), minimum_words)
                result["storyboardProvider"] = f"gemini:{model_id}"
                print(f"Creative director used Gemini ({model_id}).")
                return result
            except Exception as error:
                print(f"Gemini {model_id} unavailable; trying next provider: {error}")

    # 3) Keyless Pollinations fallback. Every request carries a fresh creative variation key.
    pollinations_error = None
    free_model = os.environ.get("POLLINATIONS_TEXT_MODEL", "openai")
    retry_prompt = f"{user_prompt}\n\nRespond with valid JSON only."
    for attempt in range(2):
        try:
            response = requests.post(
                "https://text.pollinations.ai/openai",
                headers={"Content-Type": "application/json"},
                json={
                    "model": free_model,
                    "messages": [
                        {"role": "system", "content": sys_prompt},
                        {"role": "user", "content": retry_prompt},
                    ],
                    "temperature": 0.88,
                    "max_tokens": 8192,
                    "response_format": {"type": "json_object"},
                },
                timeout=75,
            )
            if response.status_code != 200:
                pollinations_error = f"HTTP {response.status_code}: {response.text[:180]}"
                print(f"Pollinations status {response.status_code}; moving to fallback.")
                break
            raw = response.json()["choices"][0]["message"]["content"]
            result = validate_storyboard(clean_json_response(raw), minimum_words)
            result["storyboardProvider"] = f"pollinations:{free_model}"
            print(f"Creative director used keyless Pollinations ({free_model}).")
            return result
        except Exception as error:
            pollinations_error = str(error)
            print(f"Pollinations storyboard attempt {attempt + 1} failed: {error}")
            retry_prompt = (
                f"{user_prompt}\n\nThe last response failed validation. Return a fresh, "
                f"complete JSON object with at least {minimum_words} narration words and "
                "visually distinct, topic-specific scenes. Do not shorten the narration."
            )

    detail = f" Provider diagnostic: {pollinations_error}" if pollinations_error else ""
    print(f"All AI storyboard providers unavailable; using explicit degraded fallback.{detail}")
    fallback = build_fallback_storyboard(
        prompt,
        brand,
        color,
        mode,
        is_hinglish,
        min_words=minimum_words,
    )
    return validate_storyboard(fallback, 1 if script_mode else min(35, minimum_words))




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
    if os.environ.get("CINEMA_OFFLINE") == "1":
        return False
    cache = MediaAssetCache()
    cached = cache.get(
        prompt, orientation, expected_kind="video", variation=JOB_ID
    )
    if cached:
        cached_path, _ = cached
        os.makedirs(os.path.dirname(out_mp4) or ".", exist_ok=True)
        shutil.copyfile(cached_path, out_mp4)
        print(f"Using this production's cached motion clip for scene {idx}.")
        return _is_valid_mp4(out_mp4)

    os.makedirs(os.path.dirname(out_mp4) or ".", exist_ok=True)

    # First use an optional user-configured ComfyUI workflow. It may run on Colab,
    # a self-hosted GPU or another reachable machine; it is never assumed to exist.
    try:
        comfy_outputs = generate_from_environment(
            prompt,
            os.path.dirname(out_mp4) or "public/media",
            media_kind="video",
            seed=stable_visual_seed(JOB_ID, idx, prompt),
        )
        for candidate in comfy_outputs:
            if candidate.suffix.lower() == ".mp4" and _is_valid_mp4(str(candidate)):
                shutil.copyfile(candidate, out_mp4)
                if _is_valid_mp4(out_mp4):
                    cache.store(prompt, orientation, out_mp4, "video", variation=JOB_ID)
                    print(f"Generated scene {idx} motion with configured ComfyUI.")
                    return True
    except Exception as error:
        print(f"Optional ComfyUI video route unavailable for scene {idx}: {error}")

    deadline = time.monotonic() + max(15, int(os.environ.get("CINEMA_VIDEO_CLIP_TIMEOUT", "45")))
    width, height = (832, 480) if orientation == "landscape" else (480, 832)
    video_prompt = (
        f"{prompt}, topic-specific documentary cinematography, "
        "coherent physical movement, natural camera motion, no text, no watermark"
    )
    encoded_prompt = urllib.parse.quote(video_prompt, safe="")
    model = os.environ.get("CINEMA_POLLINATIONS_VIDEO_MODEL", "wan")
    video_url = (
        f"https://video.pollinations.ai/prompt/{encoded_prompt}"
        f"?model={urllib.parse.quote(model)}&width={width}&height={height}"
    )

    try:
        response = requests.get(
            video_url,
            headers={"Accept": "video/mp4"},
            timeout=(4, min(18, max(1, deadline - time.monotonic()))),
        )
        if response.status_code == 200 and len(response.content) <= 80_000_000:
            with open(out_mp4, "wb") as output_file:
                output_file.write(response.content)
            if _is_valid_mp4(out_mp4):
                cache.store(prompt, orientation, out_mp4, "video", variation=JOB_ID)
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
                sys.executable, "-c", _GRADIO_VIDEO_SCRIPT,
                os.environ.get("CINEMA_LTX_SPACE", "Lightricks/ltx-video-distilled"),
                video_prompt, str(width), str(height), out_mp4,
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
        cache.store(prompt, orientation, out_mp4, "video", variation=JOB_ID)
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

    # Optional ComfyUI workflows can return a complete batch of distinct stills.
    # Preserve up to three outputs and let the Remotion scene sequence them as a short photo essay.
    try:
        comfy_outputs = generate_from_environment(
            query,
            "public/media",
            media_kind="image",
            seed=stable_visual_seed(JOB_ID, idx, query),
        )
        batch_limit = max(1, min(5, int(os.environ.get("CINEMA_COMFY_IMAGES_PER_SCENE", "3"))))
        media_batch: list[str] = []
        for candidate in comfy_outputs:
            if (
                candidate.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}
                and candidate.is_file()
                and candidate.stat().st_size > 5_000
            ):
                relative_path = f"media/scene_{idx}_comfy_{len(media_batch) + 1}{candidate.suffix.lower()}"
                destination = os.path.join("public", relative_path.replace("/", os.sep))
                os.makedirs(os.path.dirname(destination), exist_ok=True)
                shutil.copyfile(candidate, destination)
                media_batch.append(relative_path)
                if len(media_batch) >= batch_limit:
                    break
        if media_batch:
            SCENE_MEDIA_FILES[idx] = media_batch
            print(
                f"Generated scene {idx} still batch with configured ComfyUI "
                f"({len(media_batch)} image(s))."
            )
            return media_batch[0], "image"
    except Exception as error:
        print(f"Optional ComfyUI image route unavailable for scene {idx}: {error}")

    try:
        width, height = (1280, 720) if orientation == "landscape" else (768, 1344)
        subjects = ", ".join(_visual_subject_terms(query))
        locked_prompt = (
            f"Photorealistic documentary cinematography of exactly {subjects}; "
            f"the visible subject must directly match {subjects}. {query}. "
            "Natural photographic detail, physically plausible light, real camera optics, "
            "use a scene-specific natural grade appropriate to the subject. NEGATIVE: NO anime, NO cartoon, "
            "NO illustration, NO random portrait, NO text, NO watermark, NO logo, "
            "NO collage, NO clip-art, NO unrelated subject."
        )
        encoded_prompt = urllib.parse.quote(locked_prompt, safe="")
        image_url = (
            f"https://image.pollinations.ai/prompt/{encoded_prompt}"
            f"?width={width}&height={height}&model=flux&nologo=true&seed={stable_visual_seed(JOB_ID, idx, query)}"
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
    cached = cache.get(query, orientation, variation=JOB_ID)
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
        cache.store(query, orientation, source, media_kind, variation=JOB_ID)
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

    try:
        kokoro_result = generate_kokoro_from_environment(
            cleaned_text,
            out_mp3,
            language="hi" if voice.startswith("hi-IN-") else "en",
        )
        if kokoro_result is not None:
            return kokoro_result
    except Exception as error:
        print(f"Optional Kokoro TTS route failed; continuing with Edge TTS: {error}")

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

    route = route_production_request(
        RAW_PROMPT,
        os.environ.get("FORMAT", "vertical"),
        research_enabled=not offline_mode,
    )
    if route.research_context:
        trending_context = route.research_context
    if not offline_mode and re.search(r"(?<!\S)--trending(?!\S)", RAW_PROMPT, re.IGNORECASE):
        try:
            extra_trends = fetch_trending_context()
            trending_context = "\n".join(part for part in (trending_context, extra_trends) if part)
        except requests.RequestException as error:
            print(f"Google Trends context unavailable; continuing without it: {error}")

    intent = parse_prompt_intent(
        strip_viral_flags(route.prompt),
        route.format_hint,
    )
    orientation = intent.format
    subject_text = intent.script_text if intent.input_mode == "script" else intent.prompt
    topic_kind = classify_topic(subject_text)
    is_hinglish = intent.voice.startswith("hi-IN-")
    creative_direction = build_creative_direction(
        subject_text,
        topic_kind=topic_kind,
        input_mode=intent.input_mode,
        production_style={
            "market_update": "newsroom_editorial",
            "commercial": "cinematic_commercial",
            "explainer": "visual_explainer",
            "travel": "documentary_travel",
            "story": "character_led_story",
            "technology": "technical_documentary",
            "general": "subject_led_editorial",
        }.get(topic_kind, "subject_led_editorial"),
        seed=JOB_ID,
        research_context=trending_context,
    )

    viral_plan = build_viral_plan(
        route.prompt,
        intent.mode,
        intent.duration_sec,
        trending_context=trending_context,
    )
    scene_count_instruction = f"exactly {viral_plan.scene_count}"

    sys_prompt = SYSTEM_PROMPT.format(
        target_words=intent.target_words,
        min_narration_words=max(30, intent.min_narration_words),
        scene_count_instruction=scene_count_instruction,
        lang_instruction=intent.lang_instruction,
        style_instruction=viral_plan.system_instruction,
        creative_direction=creative_direction,
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

    latest_brief = intent.script_text if intent.input_mode == "script" else intent.prompt
    full_prompt = enhance_story_prompt(
        compose_story_prompt(latest_brief, prompt_context),
        viral_plan,
    )
    full_prompt += (
        "\n\nCURRENT PRODUCTION: " + JOB_ID
        + "\nINPUT MODE: " + intent.input_mode
        + "\nTOPIC CLASS: " + topic_kind
        + "\nUse a fresh angle and distinct shots for this production."
    )

    if offline_mode:
        storyboard = build_fallback_storyboard(
            full_prompt,
            intent.brand,
            intent.color,
            intent.mode,
            is_hinglish,
            min_words=1 if intent.input_mode == "script" else intent.min_narration_words,
        )
    else:
        storyboard = generate_storyboard(
            full_prompt,
            sys_prompt,
            1 if intent.input_mode == "script" else intent.min_narration_words,
            brand=intent.brand,
            color=intent.color,
            mode=intent.mode,
            is_hinglish=is_hinglish,
            variation_key=JOB_ID,
            script_mode=intent.input_mode == "script",
        )

    # A user-supplied script is the canonical voiceover. The model only directs its visuals.
    narration_source = (
        intent.script_text if intent.input_mode == "script" else storyboard["narration"]
    )
    narration = sanitize_narration(narration_source)
    scenes = diversify_scenes(storyboard.get("scenes", []))
    scenes = assign_visual_language(scenes, topic_kind, JOB_ID, orientation)
    SCENE_MEDIA_FILES.clear()
    if not scenes:
        raise RuntimeError("Creative director returned no usable scenes.")

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

        language_code = "hi" if is_hinglish else "en"
        aligned_words = align_with_whisperx(
            "public/voiceover.mp3",
            narration,
            language=language_code,
        )
        if aligned_words:
            words = aligned_words

    total_weight = sum(float(scene.get("weight", 1.0)) for scene in scenes)
    cursor = 0.0
    timed_scenes = []
    video_scene_indexes = choose_video_scene_indexes(
        scenes,
        max_clips=max(0, min(8, int(os.environ.get("CINEMA_MAX_VIDEO_CLIPS", "5")))),
    )

    for idx, scene in enumerate(scenes):
        duration = (
            total_duration / len(scenes)
            if viral_plan.fast_cuts
            else (float(scene.get("weight", 1.0)) / max(total_weight, 1e-6)) * total_duration
        )
        scene["startSec"] = round(cursor, 2)
        cursor = total_duration if idx == len(scenes) - 1 else cursor + duration
        scene["endSec"] = round(cursor, 2)

        query = str(scene.get("visualQuery", "")).strip()
        clip_path = f"public/media/scene_{idx}.mp4"
        generated_video = (
            not offline_mode
            and idx in video_scene_indexes
            and scene.get("mediaMode") not in {"still", "graphic"}
            and try_generate_ai_video_clip(query, idx, orientation, clip_path)
        )
        if generated_video:
            media_file, media_kind = f"media/scene_{idx}.mp4", "video"
        else:
            media_file, media_kind = fetch_broll_or_ai_visual(query, idx, orientation)

        scene["mediaFile"] = media_file
        scene["mediaKind"] = media_kind
        scene["mediaFiles"] = SCENE_MEDIA_FILES.get(
            idx, [media_file] if media_file else []
        )
        scene["visualSeed"] = stable_visual_seed(JOB_ID, idx, query)
        timed_scenes.append(scene)

    # Visual audit is diagnostic: a weak asset is reported instead of being disguised as success.
    visual_report = audit_visual_plan(timed_scenes, "public")
    if visual_report.get("warnings"):
        for warning in visual_report["warnings"]:
            print(f"VISUAL QA WARNING: {warning}")

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
        "narration": narration,
        "brandTag": intent.brand,
        "themeColor": intent.color,
        "mode": intent.mode,
        "viralMode": viral_plan.archetype,
        "topicKind": topic_kind,
        "inputMode": intent.input_mode,
        "jobId": JOB_ID,
        "storyboardProvider": storyboard.get("storyboardProvider", "topic-aware-fallback"),
        "degradedMode": bool(storyboard.get("degradedMode", False)),
        "researchContext": trending_context,
        "visualQuality": visual_report,
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
    with open("public/video_data.json", "w", encoding="utf-8") as output_file:
        json.dump(output, output_file, indent=2)

    if os.environ.get("OTIO_EXPORT_ENABLED", "").casefold() in {"1", "true", "yes"}:
        try:
            if export_otio(output, "out/final.otio"):
                print("Exported OpenTimelineIO edit timeline to out/final.otio.")
        except Exception as error:
            print(f"Optional OpenTimelineIO export unavailable: {error}")

    print(
        f"Mastered {total_duration:.2f}s {intent.mode} film | "
        f"Topic: {topic_kind} | Input: {intent.input_mode} | "
        f"Scenes: {len(timed_scenes)} | AI video attempts: {len(video_scene_indexes)} | "
        f"Words: {len(words)} | Provider: {output['storyboardProvider']}"
    )

if __name__ == "__main__":
    main()
