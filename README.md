# Cinema AI Film & Reels Studio (`@Ifxreelsm_bot`)

Turn a Telegram idea, story, or supplied script into a narrated, captioned MP4:

- Natural-language requests select vertical or widescreen format, runtime, Hindi/Hinglish or English narration, and male/female voice.
- The intent router sends short prompts to a 9:16 reel and documentary or detailed prompts to a 16:9 film. Long-form requests are bounded to 2–5 minutes, with public Google News and DuckDuckGo results treated only as research leads.
- The director builds a complete narration and scene plan: 10–14 scenes for fast reels and 8–14 scenes for documentaries; supplied scripts keep their key facts and meaning.
- Edge TTS tries language-matched neural voices first; if they fail, keyless gTTS supplies speech and timestamps are estimated from the MP3 duration. FFmpeg creates an original ambient score and scene-transition effects without paid audio APIs.
- A compact `assets/audio/` vault supplies warm phonk/cinema music and transition effects. The pipeline trims voiceover pauses, detects beats, ducks music under narration, and masters the result before rendering.
- High-impact scenes try keyless AI video; keyless Archive.org and Wikimedia Commons searches accept only explicitly public-domain/CC0 footage or photos. Pollinations Flux uses topic-locked photorealistic prompts, and procedural 3D scenes remain available when providers are unavailable.
- The animated XAUUSD chart is illustrative, not a live quote feed. Image resolution depends on provider support and is not guaranteed to be 8K.
- Telegram's Bot API caps uploaded videos at 50 MB ([official `sendVideo` docs](https://core.telegram.org/bots/api/methods/sendvideo.md)). The delivery step keeps smaller renders unchanged and transcodes larger ones to a size-safe MP4 before sending.
- Short-form prompts use fast viral pacing and phonk-style procedural scoring by default. `--meme`, `--movie`/`--cinema`, `--hinglish`, and `--trending` select alternate treatments or optional Google Trends context.
- High-impact scenes try a keyless video endpoint and then a public ZeroGPU Gradio Space within one combined 45-second attempt. Clips are accepted only when they pass MP4 validation; Archive.org/Wikimedia footage, Flux stills, and procedural motion remain fallbacks.
- A Telegram chat can refine its previous brief. The Cloudflare Worker keeps only the last four prompts per chat for up to 30 days; `/forget` clears them. Without a KV binding, requests still render independently and the bot reports that memory is unavailable.

## Telegram and Cloudflare setup

The Worker needs `TELEGRAM_BOT_TOKEN`, `GITHUB_REPO`, and `GITHUB_PAT`. Set `ALLOWED_CHAT_ID` to restrict the bot to one chat. Follow-up memory is optional: without `PROMPT_CONTEXT_KV`, each prompt still queues a render and is handled independently. Bind a Cloudflare KV namespace as `PROMPT_CONTEXT_KV` to retain up to four prompts per chat for 30 days; `/forget` clears them.

The GitHub repository needs `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` secrets for delivery. `GEMINI_API_KEY` is optional and used only if the keyless Pollinations storyboard provider fails. Pollinations is free to call without a key, but its service can impose rate limits or outages; no third-party free service can be promised as unlimited. Edge TTS, FFmpeg scoring, captions, and transition sounds do not require paid API keys. GitHub Actions usage may still be subject to your account's included-minutes limits.

The public Hugging Face ZeroGPU Space is best-effort: queues, daily GPU quotas, API changes, and temporary outages can prevent clip generation. The official Wan-AI demo currently requires a separate DashScope key, so it is not used by the keyless pipeline. `--trending` fetches Google Trends RSS with a short timeout; those headlines are unverified topic hints, not factual sources.

The Worker source is not deployed automatically by this repository. Deploy it through the Cloudflare dashboard or Wrangler, configure the required Worker values, and set the Telegram bot webhook to the deployed Worker URL. KV is optional.

## Colab/Kaggle GPU worker

`notebooks/Kling_Class_GPU_Worker.ipynb` is an optional Wan 2.1 1.3B GPU worker for a Colab/Kaggle runtime. A free T4 may be available, but GPU allocation, quota, startup time, memory, and batch throughput are provider-controlled; 50–60 daily videos are not guaranteed. Telegram's `getUpdates` long polling cannot run while a webhook is set for the same bot. The notebook checks for this conflict and restricts processing to a configured chat ID. Use a dedicated bot for simultaneous Cloudflare webhook and notebook polling.

## Run and test

```powershell
npm ci
pip install -r requirements.txt
python -m unittest discover -s tests
npm test
npx tsc --noEmit
```

Video generation runs `python scripts/setup_real_audio.py` and `python scripts/generate_assets.py` before `npm run build` (or `npm run build:landscape`). FFmpeg is required for audio and media processing; GitHub Actions installs it when missing. Run `python scripts/autonomous_qa_agent.py` for tests, an isolated offline pipeline run, audio decoding checks, and a short Remotion render.
