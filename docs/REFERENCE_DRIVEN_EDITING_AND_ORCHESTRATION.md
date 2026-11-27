# Reference-Driven Editing and Workflow Orchestration

Updated: 28 November 2026.

## Product behaviour we are building

A request can contain:
- A written brief or exact narration script.
- A locally supplied reference reel/video that the user owns or has permission to analyze.
- One or more reference images, product photographs, logos or screenshots.
- A social URL used as a style pointer only. The pipeline must not download, copy, or republish the creator's video/audio. Ask for a supplied file or licensed assets when frame-level analysis is required.

The production contract should distinguish **reference intent** from **content to reproduce**. Extract pacing, aspect ratio, shot rhythm, framing, color mood, typography hierarchy and transition language. Recreate the editing grammar with original assets and copy—not a frame-for-frame clone.

## Reference analyzer added

`scripts/reference_analyzer.py` is an offline-first CLI:
- Reads local video metadata with ffprobe.
- Detects candidate cut points with FFmpeg scene detection.
- Extracts a bounded contact sheet for human/vision review.
- Reads reference image dimensions and average color with optional Pillow.
- Uses the existing `GEMINI_API_KEY` for bounded Gemini multimodal image understanding when configured, resizing images before transmission; `GEMINI_MODEL` or `CINEMA_REFERENCE_VISION_MODEL` selects the model. If no Gemini key is configured, it can call a user-configured Ollama vision model (`CINEMA_VISION_BASE_URL`, `CINEMA_VISION_MODEL`).
- Produces a machine-readable `reference_style.json` with limitations and editing guidance.
- Smart-crops reference images to vertical, landscape or square while respecting an explicit focal point or a lightweight entropy-based focal heuristic.

Important: the entropy heuristic is not semantic object detection. A production-grade crop should prefer a vision model's subject/focal-point output, then face/person detection where appropriate, then the heuristic, and finally a human override. Never crop logos, text, faces or product labels blindly.

Example:
```bash
python scripts/reference_analyzer.py --video /data/reference.mp4 --images /data/product.jpg /data/logo.png --crop-to vertical
```

Gemini vision uses the existing API key and may consume API quota or incur charges according to the Google AI plan. It only runs when a reference attachment is present. To avoid external image transmission, omit the Gemini key for the analysis step and configure a private Ollama vision endpoint instead:
```bash
ollama pull qwen2.5vl:3b
CINEMA_VISION_MODEL=qwen2.5vl:3b python scripts/reference_analyzer.py --images /data/reference.jpg
```
Model availability and VRAM requirements vary; test on the actual host before enabling it. Vision is optional and is not a requirement for CPU editorial rendering.

## Telegram reference ingestion now wired

The current branch adds a first end-to-end attachment path:
1. Telegram Worker accepts a photo, video, or image/video document with optional caption.
2. It sends the Telegram file ID, media kind and MIME type through the private GitHub repository-dispatch payload. It never sends the file bytes or bot token in that payload.
3. GitHub Actions uses the existing Telegram bot secret to call getFile and download the user-supplied attachment directly into the ephemeral runner.
4. The downloader enforces a 20 MB cap, extension/MIME allowlists, temporary-file writes and size verification. It never prints the tokenized download URL.
5. The analyzer creates reference style JSON. A reference image is focal-point fitted and inserted into the best-matching scene (first scene when no semantic match is available); reference video contributes pacing and cut-rhythm direction, not copied footage.
6. The storyboard prompt receives the extracted style cues, and the output remains the studio's original narration and edit.

This path does not require an R2 bucket for a single Telegram attachment. It is limited by Telegram Bot API download size and a single attachment per message. Telegram albums/multiple reference attachments, malware scanning, OCR-specific validation and a human crop-preview approval flow remain future work. The GitHub runner is ephemeral; downloaded source media is not persisted in a public bucket.

Do not store Telegram bot tokens or tokenized download URLs in artifacts/logs. User-supplied media rights still need to be checked before commercial publishing.

## Reference-image crop contract

Every shot should carry:
- source asset ID and rights/provenance record;
- source dimensions and intended output aspect;
- focal point (normalized x/y), subject boxes when available;
- fit mode (cover/contain/blurred-background), crop rectangle and safe zones;
- OCR/text/logo protection flags;
- crop preview and human override.

Recommended fit order:
1. Semantic vision detects the main subject, product and text/logo regions.
2. Face/person detection is used only when it improves the shot and is permitted.
3. Crop solver finds the largest target-aspect rectangle containing the focal subject and protected regions.
4. If no safe crop exists, use contain + designed background, split layout or blurred extension—never distort/stretch.
5. Generate a contact sheet and run QA for clipped faces, labels, logos and captions.

## Orchestration decision: Dagu vs Kestra vs Temporal

| Engine | Strength | Operational footprint | Best fit here |
|---|---|---|---|
| Dagu | Single binary, YAML DAGs, built-in UI, retries, local/remote workers; no external DB/broker for simple self-hosting | Lowest | First benchmark candidate for the current script-based studio |
| Kestra | Rich event-driven workflows, plugins, control/data plane and distributed workers | Higher; backend/queue/database configuration | Consider when many integrations, teams, backfills and hybrid worker fleets justify it |
| Temporal | Durable execution in application code; strong recovery for long-running workflows and complex signals/timers | Requires a Temporal service and application worker code; greater engineering commitment | Consider when the studio becomes a multi-tenant product with long-lived jobs, human approvals and complex resumability |

Decision:
- Keep GitHub Actions as the current CI and Telegram dispatch executor while it is reliable.
- Benchmark Dagu first as an optional self-hosted DAG runner; do not install Dagu, Kestra and Temporal together.
- Do not migrate the render pipeline to Temporal just because workflows can run for years. The studio's primary problem today is shot quality and reference ingestion, not multi-year durable business transactions.
- Dagu's GPL-3.0-or-later applies to Dagu itself. Running it internally as a separate process does not automatically make workflow scripts GPL; do not embed its Go library in a distributed proprietary binary without a licence review.
- Kestra's OSS architecture separates control plane and workers; confirm edition-specific security features and infrastructure needs before deployment.
- Temporal's durable execution is powerful but requires a real workflow application and service; it is not a drop-in YAML scheduler.

## Reproducible orchestration benchmark

Run the same synthetic production DAG 20 times on the same VPS and record:
- cold-start and warm-start time;
- median and p95 end-to-end duration;
- retry/resume behaviour after killing a worker mid-step;
- concurrency/backpressure under 1, 3 and 5 simultaneous jobs;
- persisted history and log retention;
- CPU/RAM/disk idle and peak usage;
- secret masking and worker authentication;
- install/upgrade/backup effort;
- licence and any edition-gated capabilities.

Workload: validate manifest → analyze reference → render a 5-second offline test → probe output → package artifacts. Use identical scripts and inputs for each engine. A Dagu DAG starter is in `orchestration/dagu/cinema-reference-analysis.yaml`. This repository change does not claim that Dagu has been installed on the user's VPS or benchmarked at runtime; remote host access and an approved deployment window are required.

## Sources

- Dagu project and architecture: https://github.com/dagucloud/dagu
- Dagu licence FAQ: https://docs.dagu.sh/overview/licensing-faq
- Kestra architecture: https://kestra.io/docs/architecture
- Temporal durable execution: https://docs.temporal.io/temporal
