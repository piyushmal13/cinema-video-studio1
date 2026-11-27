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

\`scripts/reference_analyzer.py\` is an offline-first CLI:
- Reads local video metadata with ffprobe.
- Detects candidate cut points with FFmpeg scene detection.
- Extracts a bounded contact sheet for human/vision review.
- Reads reference image dimensions and average color with optional Pillow.
- Can call a user-configured Ollama vision model (\`CINEMA_VISION_BASE_URL\`, \`CINEMA_VISION_MODEL\`) for image descriptions. Default is local Ollama; no image is sent anywhere unless the operator explicitly configures a remote endpoint.
- Produces a machine-readable \`reference_style.json\` with limitations and editing guidance.
- Smart-crops reference images to vertical, landscape or square while respecting an explicit focal point or a lightweight entropy-based focal heuristic.

Important: the entropy heuristic is not semantic object detection. A production-grade crop should prefer a vision model's subject/focal-point output, then face/person detection where appropriate, then the heuristic, and finally a human override. Never crop logos, text, faces or product labels blindly.

Example:
\`\`\`bash
python scripts/reference_analyzer.py --video /data/reference.mp4 --images /data/product.jpg /data/logo.png --crop-to vertical
\`\`\`

For local vision:
\`\`\`bash
ollama pull qwen2.5vl:3b
CINEMA_VISION_MODEL=qwen2.5vl:3b python scripts/reference_analyzer.py --images /data/reference.jpg
\`\`\`
Model availability and VRAM requirements vary; test on the actual host before enabling it. The user's known 4 GB AMD GPU is not a dependable modern video-diffusion target. The vision call is optional and is not a requirement for CPU editorial rendering.

## Next integration gate

The analyzer is deliberately a safe, testable foundation—not yet a claim that Telegram attachments are persisted or that every render consumes reference media automatically. The next integration requires:
1. Telegram Worker support for photo/video/document messages.
2. Private object storage (Cloudflare R2 or equivalent) with size/type limits and expiring signed URLs.
3. A manifest passed to GitHub Actions by opaque object key, never raw binary or public Telegram file tokens.
4. Download and malware/type/size validation in the production runner.
5. Reference style JSON fed into creative direction and per-shot crop metadata fed into Remotion.
6. A contact-sheet approval/edit step for high-impact commercial work.

Do not expose R2 buckets or reference media publicly by default. Do not store Telegram bot tokens or signed URLs in artifacts/logs.

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

Workload: validate manifest → analyze reference → render a 5-second offline test → probe output → package artifacts. Use identical scripts and inputs for each engine. A Dagu DAG starter is in \`orchestration/dagu/cinema-reference-analysis.yaml\`. This repository change does not claim that Dagu has been installed on the user's VPS or benchmarked at runtime; remote host access and an approved deployment window are required.

## Sources

- Dagu project and architecture: https://github.com/dagucloud/dagu
- Dagu licence FAQ: https://docs.dagu.sh/overview/licensing-faq
- Kestra architecture: https://kestra.io/docs/architecture
- Temporal durable execution: https://docs.temporal.io/temporal
