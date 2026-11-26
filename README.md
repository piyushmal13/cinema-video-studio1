# Cinema AI Film & Reels Studio (`@Ifxreelsm_bot`)

Turn a Telegram idea, story, or supplied script into a narrated, captioned MP4:

- Natural-language requests select vertical or widescreen format, runtime, Hindi/Hinglish or English narration, and male/female voice.
- The director builds a complete narration and 5–7 scenes; supplied scripts keep their key facts and meaning.
- Free Edge TTS speech and word timings drive the narration and captions. FFmpeg creates an original ambient score and scene-transition effects without paid audio APIs.
- Pollinations generates topic-specific images without an API key; cinematic gradients and procedural 3D scenes keep renders working when image generation is unavailable.
- A Telegram chat can refine its previous brief. The Cloudflare Worker keeps only the last four prompts per chat for up to 30 days; `/forget` clears them. Without a KV binding, requests still render independently and the bot reports that memory is unavailable.

## Telegram and Cloudflare setup

The Worker needs `TELEGRAM_BOT_TOKEN`, `GITHUB_REPO`, and `GITHUB_PAT`. Set `ALLOWED_CHAT_ID` to restrict the bot to one chat. Follow-up memory is optional: without `PROMPT_CONTEXT_KV`, each prompt still queues a render and is handled independently. Bind a Cloudflare KV namespace as `PROMPT_CONTEXT_KV` to retain up to four prompts per chat for 30 days; `/forget` clears them.

The GitHub repository needs `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` secrets for delivery. `GEMINI_API_KEY` is optional and used only if the keyless Pollinations storyboard provider fails. Pollinations is free to call without a key, but its service can impose rate limits or outages; no third-party free service can be promised as unlimited. Edge TTS, FFmpeg scoring, captions, and transition sounds do not require paid API keys. GitHub Actions usage may still be subject to your account's included-minutes limits.

The Worker source is not deployed automatically by this repository. Deploy it through the Cloudflare dashboard or Wrangler, configure the required Worker values, and set the Telegram bot webhook to the deployed Worker URL. KV is optional.

## Run and test

```powershell
npm ci
pip install -r requirements.txt
python -m unittest discover -s tests
npm test
npx tsc --noEmit
```

Video generation runs `python scripts/generate_assets.py` before `npm run build` (or `npm run build:landscape`). FFmpeg must be installed for the free score and transition effects; the GitHub Actions render workflow installs it when missing.
