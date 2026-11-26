# Cinema AI Film & Reels Studio (`@Ifxreelsm_bot`)

Turn a Telegram idea, story, or supplied script into a narrated, captioned MP4:

- Natural-language requests select vertical or widescreen format, runtime, Hindi/Hinglish or English narration, and male/female voice.
- The director builds a complete narration and 5–7 scenes; supplied scripts keep their key facts and meaning.
- Free Edge TTS speech and word timings drive the narration and captions. FFmpeg creates an original ambient score and scene-transition effects without paid audio APIs.
- AI-generated images are optional; cinematic gradients and procedural 3D scenes keep the film renderable when image generation is unavailable.
- A Telegram chat can refine its previous brief. The Cloudflare Worker keeps only the last four prompts per chat for up to 30 days; `/forget` clears them. Without a KV binding, requests still render independently and the bot reports that memory is unavailable.

## Telegram and Cloudflare setup

The Worker needs the existing `TELEGRAM_BOT_TOKEN`, `GITHUB_REPO`, and `GITHUB_PAT` environment values. Set `ALLOWED_CHAT_ID` to restrict the bot to one chat. To enable follow-up context, create a Cloudflare KV namespace and bind it to the Worker as `PROMPT_CONTEXT_KV`. Context is scoped by chat ID, expires after 30 days, and can be removed with `/forget`.

The GitHub repository needs `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` secrets for video delivery. `GEMINI_API_KEY` and `GROQ_API_KEY` are optional; when absent, the generator tries its keyless text provider. Edge TTS, FFmpeg scoring, captions, and transition sounds do not require paid API keys. GitHub Actions usage may still be subject to your account's included-minutes limits.

The Worker source is not deployed automatically by this repository. Deploy it through the Cloudflare dashboard or Wrangler after configuring its existing secrets and the KV binding.

## Run and test

```powershell
npm ci
pip install -r requirements.txt
python -m unittest discover -s tests
npm test
npx tsc --noEmit
```

Video generation runs `python scripts/generate_assets.py` before `npm run build` (or `npm run build:landscape`). FFmpeg must be installed for the free score and transition effects; the GitHub Actions render workflow installs it when missing.
