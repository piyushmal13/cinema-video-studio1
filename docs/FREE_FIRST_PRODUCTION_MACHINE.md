# Free-First Production Machine: Technical Research and Operating Plan

Research snapshot: 27 November 2026. This extends the existing Telegram-first Cinema Studio; it is not a replacement architecture.

## Executive decision

Keep Cloudflare Worker → GitHub Actions → Python creative/research/media pipeline → Remotion/FFmpeg → Telegram. Add an optional GPU worker, hardware-aware routing, repository scouting and measured job telemetry. Do not migrate everything into a large agent framework.

The honest target is zero paid API subscriptions for the default workflow, not unlimited zero-cost photorealistic video generation. Open-source software does not pay for GPU time, storage, bandwidth, electricity or model downloads. Free hosted GPUs are quota-based and may be unavailable.

## Existing architecture audit

Already on main:
- Telegram prompt dispatch through Cloudflare Worker and GitHub repository_dispatch.
- Python creative director, topic-specific skills, research route, visual director and media cache.
- Best-effort public media, Pollinations and a ZeroGPU video route.
- Wan2.1 1.3B Colab/Kaggle worker notebook.
- Edge TTS/gTTS, optional Kokoro, optional WhisperX, FFmpeg audio finishing.
- Remotion render, visual QA, post-production package and Telegram delivery.
- Optional ComfyUI API adapter and OpenTimelineIO export.

Gaps:
1. No durable queue with backpressure, worker heartbeats, leases and cancellation across GPU workers.
2. No measured per-job compute/asset ledger or capacity-aware admission control.
3. No automated repository discovery and security/licence review workflow.
4. No robust semantic verification that each selected image actually depicts its assigned shot.
5. No pinned model registry with weight licence, revision, VRAM, quantization and tested hardware.
6. GitHub runner performs orchestration and CPU rendering; it is not a diffusion GPU host.
7. Notebook polling is opportunistic, not a durable always-on service.

## Specialist brain hierarchy

These are bounded specialist modules coordinated by one deterministic state machine—not an uncontrolled swarm of LLM calls.

| Brain | Responsibility | Deliverable / gate |
|---|---|---|
| Executive Producer | Interpret prompt, platform, audience, duration and constraints | Production contract |
| Research Librarian | Retrieve primary sources, timestamps, licence and citations | Evidence ledger |
| Subject Expert | Challenge terminology, logic and unsupported claims | Fact-check report |
| Script Doctor | Hook, act progression, clarity, voice rhythm and word/time budget | Narration |
| Story Editor | Convert narration into purposeful shots and continuity | Shot list |
| Visual Director | Composition, palette, camera, lens language and media method | Per-shot render plan |
| Asset Researcher | Find licensed/public-domain footage and images, record attribution | Rights-aware asset manifest |
| Generation Supervisor | Choose ComfyUI/Wan/model based on capability and GPU capacity | Bounded generation jobs |
| Audio Director | TTS, pronunciation, timing, music ducking, loudness and SFX | Audio stems and cue sheet |
| Editor | Assemble rhythm, transitions, titles, captions and grade | Timeline and master |
| Critic / QA | Check narrative, semantic match, repetition, black frames, freezes, sync and rights | Pass/fail with targeted fixes |
| Cost & Capacity Brain | Estimate duration, queue and resource envelope | Admission decision |
| Repository Scout | Discover projects, inspect health/licence/security, propose adapters | Ranked candidates; never auto-execute |
| Release Engineer | Pin versions, run tests and open rollback-safe PR | CI-verified change |

Use deterministic Python for routine steps. Typical short videos need one planner pass and a conditional critic pass—not fourteen paid LLM calls. Parallelise asset retrieval and independent shot generation. Each brain returns typed output, confidence, provenance and failure state.

## Pipeline state machine

queued → contract → research (conditional) → script → storyboard → asset_plan → asset_fetch/generate → voice/audio → edit_plan → render → technical_QA → semantic_QA → package → Telegram delivery → archived.

Every stage needs an idempotency key, timeout, bounded retries, checkpoint artifact and structured logs. A failed GPU job must not regenerate script or voiceover. Resume from the failed stage.

## Provider routing policy

1. Use existing licensed footage and stills for documentary/news/explainers when they are more truthful than generated footage.
2. Use procedural Remotion/FFmpeg graphics for diagrams, charts, maps, timelines and UI.
3. Use a local image model for keyframes/consistent characters when a GPU worker exists.
4. Use image-to-video for hero/action shots, not every scene.
5. Use text-to-video only when motion is central and a worker has enough VRAM.
6. With no GPU, create a polished editorial film with sourced assets, parallax, typography, charts and audio. Never pretend CPU pan/zoom is AI-generated motion.

## Candidate repositories and decisions

| Project | Contribution | Decision | Constraint |
|---|---|---|---|
| Dagu — https://github.com/dagucloud/dagu | Lightweight self-hosted DAG scheduler, UI, retries, SSH/Docker tasks | Best future scheduler candidate if Actions outgrows the queue | Do not add until persistent workers are required |
| Kestra — https://github.com/kestra-io/kestra | Rich event and data workflow orchestration | Strong alternative at larger scale | More operational footprint; do not install both Dagu and Kestra |
| ComfyUI — https://github.com/Comfy-Org/ComfyUI | Node-based model execution and API workflows | Keep as GPU execution adapter | GPL-3.0 project; nodes and weights have separate terms |
| Wan2.2 — https://github.com/Wan-Video/Wan2.2 | Improved image/text-to-video family | Evaluate TI2V 5B on an available NVIDIA GPU | Not suitable for current 4 GB AMD workstation |
| LTX-2.5 — https://github.com/Lightricks/LTX-2 | New multi-shot audio/video generation | Research candidate for a dedicated worker | Model weights have a separate community licence; verify before commercial use |
| ai-video-pipeline — https://github.com/06pratyush/ai-video-pipeline | Wan2.2, keyframes, ComfyUI, RIFE, Kokoro, Whisper and FFmpeg reference | Study its patterns and benchmark method; do not wholesale copy | Project reports 8 GB NVIDIA / 16 GB RAM minimum; validate independently |
| OpenTimelineIO — https://github.com/AcademySoftwareFoundation/OpenTimelineIO | Portable timeline interchange | Keep current adapter | Timeline format, not a renderer |
| WhisperX — https://github.com/m-bain/whisperX | Word-level alignment and diarization | Optional GPU worker enhancement | Heavy dependencies |
| RIFE — https://github.com/hzwer/ECCV2022-RIFE | Frame interpolation | Optional finishing stage | Extra compute; can introduce artefacts |
| Real-ESRGAN — https://github.com/xinntao/Real-ESRGAN | Upscaling/restoration | Optional only for selected low-res assets | Avoid upscaling every scene |
| FFmpeg — https://ffmpeg.org/ | Encode, trim, mix, composite, loudness and probe | Core low-cost renderer | Build flags affect LGPL/GPL obligations |
| Motion Canvas — https://github.com/motion-canvas/motion-canvas | Code-driven explainer animation | Evaluate only if Remotion cannot cover a specific need | Avoid parallel animation frameworks without a clear win |

Do not adopt HunyuanVideo 13B as a free default: its official README reports approximately 45–60 GB peak GPU memory for documented settings. This is datacenter-class hardware, not a casual free notebook assumption.

## Compute reality and current workstation

Known workstation: Ryzen 5 5600GT, 16 GB RAM and AMD Radeon 4 GB.
- Good for Telegram orchestration, Python planning, FFmpeg/Remotion editorial rendering at modest resolution.
- Small quantized LLMs only after measuring memory; Ollama on a separate reachable host is often better.
- Not a realistic local Wan/LTX/Hunyuan diffusion host.
- AMD support depends on OS, drivers, ROCm/DirectML and model-specific kernels. A 4 GB card must not be promised modern video diffusion.
- Hardware doctor reports actual host capabilities; never infer usable VRAM from product marketing.

Free compute channels:
- GitHub Actions: standard hosted runner usage is free for public repositories under GitHub's policy; use for tests, orchestration, CPU assembly and light rendering—not diffusion.
- Kaggle notebooks: free GPU may be available (documented P100 option), but queue and quota availability are not guaranteed.
- Google Colab: free GPU access and runtime limits fluctuate; sessions can terminate. Treat it as opportunistic.
- Personal PC/VPS: persistent, but electricity, storage, bandwidth and VPS rental are real costs.
- Never rotate accounts, evade quotas, scrape tokens or keep free sessions alive against provider rules.

## Cost model: measure, never invent

Track queue wait, CPU wall time, GPU seconds, peak VRAM, RAM, model downloads, input/output bytes, source provenance, render duration, retries, provider and quota class.

Cash cost:
- Hosted compute = billable seconds × actual provider rate.
- Storage = GB-month × provider rate.
- Egress = GB × provider rate.
- Electricity = kWh × local tariff.
- API = actual request/token/second invoice.
- Human review = review minutes × internal hourly cost.

If billing data is absent, cash cost remains null—not zero. Free quota is zero cash only within its terms; it is not zero economic cost.

## Rendering strategy

- Remotion for React compositions, kinetic typography, choreography and reusable components.
- FFmpeg directly for trim, concat, scale/crop, audio mix, loudness, fades and simple overlays.
- CPU still-image motion path when no GPU is available.
- Draft at 540x960 or lower; master at 720x1280 or 1080x1920 only when source quality and render budget justify it.
- Use hardware encoding only if the runner exposes a compatible encoder; otherwise tune libx264 preset for time/quality.
- Prefer one coherent keyframe per shot and animate it over demanding multiple expensive AI stills per scene by default.
- Cache immutable downloads by content hash and source URL; retain attribution, licence and retrieval timestamp.
- Reuse TTS only when script hash, voice, model revision, language, speed and pronunciation dictionary all match.

## Licence and compliance gates

Software licence != model-weight licence != dataset licence != output rights.
- Remotion's current pricing page says its Free License covers individuals and companies up to 3 people, including automation; its Automators plan is $0.01/render with $100/month minimum where the Free License does not apply. Verify eligibility and terms before commercial scale.
- Wan, LTX, Hunyuan and TTS weights have their own terms. Do not assume inference code's licence also applies to weights.
- Public-domain/Creative Commons media needs source URL, creator, licence, attribution requirement and retrieval timestamp.
- Do not scrape/rehost copyrighted music, stock footage, news imagery or social videos without permission.

## Phased implementation

### Phase A — no new GPU required
- Repository scout with licence/activity/archive triage; never auto-install.
- Hardware doctor for actual CPU/RAM/GPU/FFmpeg capability.
- Production ledger for wall time, asset sizes, providers and degraded mode.
- Keep Telegram/Actions route.
- CI tests deterministic code and a short offline render, never downloads huge model weights.

### Phase B — opportunistic free GPU worker
- One ComfyUI/Wan worker with health endpoint, job ID, lease, heartbeat, max queue and cancellation.
- Cloudflare webhook dispatches job ID to queue; GPU worker polls queue. Keep one polling bot only if no webhook conflict.
- Use Kaggle/Colab only while user starts a session and quota is available. If worker heartbeat is absent, fall back to CPU editorial.
- Pin checkpoint hashes and ComfyUI workflow versions.

### Phase C — quality intelligence
- Semantic shot-to-asset matching with a local CLIP/SigLIP model when CPU/GPU budget permits.
- Contact sheets, black-frame/freeze detection, scene boundaries, loudness/true-peak, subtitle overlap and audio sync checks.
- Critic reviews storyboard and sampled frames; regenerate only failed shots.
- Maintain style bibles and reference images only when continuity is requested.

### Phase D — scale only when demand proves it
- Evaluate Dagu as one scheduler, not another overlapping automation stack.
- Add Postgres/Redis only when concurrent jobs and durable worker leases require them.
- Build cost dashboard from JSONL ledger before paying for GPU rental.
- Benchmark every model on the same three-shot suite: prompt adherence, motion coherence, visual quality, seconds/clip, peak VRAM, failure rate, licence and total cost.

## Non-negotiable go/no-go rules

- No model enters production without pinned revision, weight licence, hardware benchmark, timeout and fallback.
- Repository scout never executes discovered code.
- No video ships if technical QA fails, sources are missing or factual claims lack evidence.
- Never rerender the whole film for one failed asset; resume at the failed node.
- No paid compute by default. Require explicit budget cap and kill switch.
