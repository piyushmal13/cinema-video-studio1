# Cinema AI Film & Reels Studio

Telegram-first video production built on the existing Cloudflare Worker, GitHub Actions, Python, FFmpeg, Remotion and optional Colab/Kaggle Wan worker. This upgrade improves the current pipeline incrementally rather than replacing the working infrastructure.

## Telegram prompt understanding

The creative director routes messages into distinct production modes:

- Brief to video: a short topic or rough instruction becomes original narration, creative direction and a scene-by-scene storyboard. The Telegram command itself is not used as voiceover.
- Script to video: text after an explicit SCRIPT:, VOICEOVER: or NARRATION: marker is treated as the supplied script. Longer clean narration may also be detected as a script. The supplied text becomes the canonical voiceover; the model directs the visuals around it.
- Current market update: a market topic combined with a current-update request routes to the vertical newsroom director and a bounded research pass.
- Other production styles: commercial, explainer, travel, narrative, technology and general editorial briefs use their own creative instructions.
- Follow-up edits: the Worker passes earlier prompts only when the latest message clearly reads as a follow-up. /forget clears saved context.

Roman Hindi/Hinglish is detected from common words as well as explicit Hindi / Hinglish hints. English remains the default when the language is ambiguous.

## Creative and visual production

The generator coordinates the creative director, research director, scene timing, media providers, speech generation, audio mastering and video-data output.

- scripts/creative_director.py classifies the topic, distinguishes briefs from supplied scripts, builds subject-specific creative direction and repairs duplicate visual queries inside one storyboard.
- prompts/skills contains dedicated market-update, general editorial, commercial, explainer, travel, story and technology skills.
- Provider order: reachable self-hosted Ollama when configured; configured Gemini when a key is supplied and PREFER_GEMINI is enabled; then keyless Pollinations. Provider limits and failures are recorded in storyboardProvider and degradedMode.
- The degraded fallback is topic-specific and shorter than the former fixed 12-scene generic template. It is explicitly marked as degraded rather than presented as a normal AI-written script.
- Every Telegram production receives a unique request ID. Media cache entries are scoped to the production, so an image from an earlier video is not silently reused just because the visual query is identical.
- Generated-motion attempts are spread across opening, middle and ending scenes instead of being hard-coded to positions 0 and 2. GitHub Actions now attempts up to five generated-motion clips per production (subject to provider availability and timeouts). Other scenes can use subject-matched footage, still photography or scene graphics.
- Media sources remain bounded and best-effort: Pollinations video/image endpoints, the existing Lightricks ZeroGPU Space, Archive.org and Wikimedia Commons public-domain/CC0 media. Free providers can queue, rate-limit or change availability.
- Added scene families include editorial montage, kinetic typography, process diagrams and data-viz. 3D bar visuals only render when real barValues are supplied; the renderer no longer invents chart numbers.
- IFXTrades branding is opt-in. It is applied only when the current request names IFXTrades / IndiaFXTrades or supplies an explicit brand option.

## Visual storytelling and editorial grammar

The visual director and Remotion renderer are now separate systems. The storyboard controls the subject, action and narrative beat; the visual director assigns a scene-specific composition, camera grammar, caption treatment and transition. It prevents a topic-aware script from being flattened into one centred title card.

- Fifteen distinct composition systems are available: full-bleed hero, documentary lower-third, asymmetric editorial split, magazine cover, kinetic type, vertical timeline, process blueprint, comparative split, source-data stage, market chart, orbital stage, cinema end frame, immersive photo, photo essay and side-caption.
- The treatment is selected with scene meaning in mind, then adjusted across the sequence to avoid repeating the previous two compositions. Camera movement now includes tilts, diagonal drift, handheld and intentional static holds as well as push/pan/zoom.
- Each image scene can use a ComfyUI batch of up to three stills by default. The renderer crossfades through the returned photo set during that scene. Configure COMFYUI_IMAGE_WORKFLOW to return multiple images and set CINEMA_COMFY_IMAGES_PER_SCENE (1–5) to control the batch size. Providers that return one still continue to work unchanged.
- Documentary and photo-essay scenes use lighter image grading and restrained lower-thirds; data, blueprint and comparison scenes use their own information layouts. Subtitles adapt between minimal, documentary, karaoke and newsroom ticker treatments.
- The visual QA report now counts unique composition systems and flags repeated neighbouring layouts as well as duplicate media. A quality report is diagnostic and cannot certify that a stock or generated image is semantically perfect.

The default GitHub runner still uses best-effort public media and the existing AI providers. A configured ComfyUI image workflow can create a larger coherent photo batch on a GPU host; the repository does not silently download large checkpoints or assume GPU hardware.

## Market research and source discipline

Current market requests use a separate route from general explainers. The public data pass requests indicative Yahoo Finance quotes for GC=F gold futures, the US Dollar Index, US 10-year Treasury yield, NIFTY 50 and NASDAQ Composite, then adds bounded Google News RSS / DuckDuckGo context. Quote timestamps and available sources are carried into the production context.

GC=F is a gold futures contract, not XAUUSD spot. Public quote endpoints may be delayed, stale outside market hours or unavailable. RSS headlines and search summaries are leads, not confirmed evidence by themselves. This route does not yet provide a complete licensed economic-calendar feed or a guaranteed live XAUUSD spot feed. When reliable information is unavailable, the video must say so rather than invent exact values. Market commentary is general information, not a personalised trading recommendation.

## Audio, post-production and publishing

- Edge TTS is the primary neural voice and gTTS remains the no-key fallback. FFmpeg creates ambient score and transition effects, trims pauses, mixes/ducks music and masters the audio.
- scripts/speech_alignment.py can use WhisperX for word-level alignment when explicitly enabled; otherwise existing TTS word timings remain active.
- scripts/timeline_export.py can export an OpenTimelineIO .otio timeline when the optional package is installed and OTIO_EXPORT_ENABLED=1.
- scripts/visual_quality.py checks media coverage, missing assets, duplicate queries/media and basic rendered stream/duration integrity. It is a diagnostic quality gate, not an AI detector or a guarantee of photorealism.
- scripts/post_production.py generates the topic-specific publishing package, platform caption, hashtags, source URLs and cover frame. Telegram delivery uses the generated caption and attaches the cover when it meets the thumbnail-size limit.
- Large MP4s retain the existing temporary-link fallback. Those links are public and expire after 48 hours.

## Optional free integrations

The six external open-source integrations, implementation status, licence notes and environment variables are inventoried in docs/FREE_OPEN_SOURCE_AI_STACK.md.

The default pipeline remains lightweight. Large model weights are not installed in every GitHub Actions run.

### Ollama
Set OLLAMA_BASE_URL to a reachable Ollama server and OLLAMA_MODEL to a model already pulled on that machine, e.g. gemma4:26b. A private Tailscale endpoint is suitable if the GitHub/Colab execution environment can reach it. The director falls through to Gemini/Pollinations if Ollama is unavailable.

### ComfyUI
scripts/comfyui_client.py uses the ComfyUI API workflow format. Configure a reachable ComfyUI server and provide your own workflow JSON and model/node packs:
- COMFYUI_BASE_URL
- COMFYUI_VIDEO_WORKFLOW for video
- COMFYUI_IMAGE_WORKFLOW for still images
- optional COMFYUI_VIDEO_MAPPING / COMFYUI_IMAGE_MAPPING JSON files for positive, negative and seed node IDs
- COMFYUI_TIMEOUT_SECONDS (default 240)

The adapter does not download large checkpoints or install arbitrary custom nodes. Without a reachable server and compatible workflow, existing Pollinations / public-media fallbacks remain active.

### WhisperX, OpenTimelineIO and Kokoro
These are optional packages listed in requirements-optional.txt; they are not installed in the default GitHub Actions pipeline. Install only what the chosen worker needs. Set WHISPERX_ENABLED=1 to enable WhisperX alignment and OTIO_EXPORT_ENABLED=1 to write out/final.otio. Kokoro ONNX is an optional local TTS provider for English and Hindi when model/voice files are installed and KOKORO_TTS_ENABLED=1; otherwise Edge TTS and gTTS remain automatic fallbacks. Model-weight and voice terms must be checked separately from software licences.

## Telegram and Cloudflare setup

The Worker needs TELEGRAM_BOT_TOKEN, GITHUB_REPO and GITHUB_PAT. Set ALLOWED_CHAT_ID to restrict access. Bind PROMPT_CONTEXT_KV to retain the last four prompts per chat for up to 30 days; /forget clears the saved context. Every request includes a unique request_id.

The GitHub repository needs TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID secrets. GEMINI_API_KEY is optional and may use a free-tier key, but quotas and model availability are provider-controlled. Pollinations, public Hugging Face Spaces and temporary media hosts are best-effort; no free service promises unlimited throughput or uptime.

The Worker source is not automatically deployed by GitHub Actions. Deploy it through the Cloudflare dashboard or Wrangler, configure its secrets/KV binding and set the Telegram bot webhook to the deployed Worker URL.

## Colab / Kaggle GPU worker

notebooks/Kling_Class_GPU_Worker.ipynb remains the optional Wan 2.1 1.3B worker for Colab/Kaggle GPU runtimes. It preserves the existing sequential Telegram polling flow and local Wan callback while using the improved creative storyboard, market research, job-scoped media and post-production functions from this repository.

A free T4 allocation, quota, runtime duration, memory and throughput are not guaranteed. Telegram getUpdates polling cannot operate while the same bot has a webhook configured. Use a separate bot for simultaneous Cloudflare webhook and notebook polling. Do not assume Colab/Kaggle session storage is persistent.

Wan 2.2 TI2V-5B and larger models are not selected by default because their GPU memory requirements exceed what the existing free T4 workflow can reliably provide.

## Run and test

Run npm ci, install requirements.txt, then run:
- python -m unittest discover -s tests
- npm test
- npx tsc --noEmit

Video generation runs scripts/setup_real_audio.py and scripts/generate_assets.py before npm run build (or npm run build:landscape). GitHub Actions installs FFmpeg when missing. Run scripts/autonomous_qa_agent.py for unit tests, an isolated offline pipeline run, audio decoding checks and a short Remotion render.


## Free-first production intelligence

Read [docs/FREE_FIRST_PRODUCTION_MACHINE.md](docs/FREE_FIRST_PRODUCTION_MACHINE.md) for the architecture audit, compute limits, candidate repositories, licence gates and phased roadmap.

Optional tools:
- python scripts/hardware_doctor.py — read-only CPU/RAM/GPU/FFmpeg capability report; no model downloads or driver changes.
- python scripts/repo_scout.py --limit 30 — ranks GitHub repositories by licence signal, stars, recency and archive status. It never clones or executes results. Set GITHUB_TOKEN for higher API limits.
- python scripts/cost_ledger.py --output out/final.mp4 --video-data public/video_data.json — records measured duration, file sizes, providers and degraded-mode state. Unknown cash costs stay null, not zero.
