# Video Model, Compute and Licence Matrix — 27 November 2026

This document is a decision aid for the existing Cinema Video Studio. It is not a claim that every model is installed or currently available as a hosted endpoint. Re-check upstream model cards, weight terms and hardware at deployment time.

## Executive finding

There is no truly unlimited, reliable, free hosted GPU. A free-first pipeline is possible if the default output does not depend on text-to-video diffusion. Use licensed footage, generated stills, procedural motion graphics, Remotion and FFmpeg for the baseline; dispatch expensive motion generation only to an available worker and accept a polished fallback when no GPU is free.

## Compute classes

| Host | Practical role | Limits / policy |
|---|---|---|
| Current Ryzen 5 5600GT, 16 GB RAM, 4 GB AMD graphics | Orchestration, small local models if measured, FFmpeg, Remotion | Do not schedule modern diffusion on 4 GB VRAM |
| GitHub Actions hosted runner | Tests, Python orchestration, asset prep, CPU assembly | No guaranteed GPU; avoid diffusion workloads |
| Kaggle free notebook | Opportunistic GPU worker and experiments | Official docs list P100 GPU sessions, 12-hour session ceiling, queue/quota availability; not an always-on worker |
| Google Colab free | Interactive experiments / manually started worker | Resources, GPU type, idle timeouts and usage limits are dynamic; not guaranteed |
| Dedicated NVIDIA GPU | Persistent high-throughput generation | Not free; budget only after measured demand |
| Existing CPU VPS | Queue/API, cache, health checks and metadata | Not a substitute for GPU diffusion |

Sources: Kaggle notebook documentation and GPU tips; Colab FAQ.

## Model selection

### Wan 2.2

- Official repository: https://github.com/Wan-Video/Wan2.2
- Official model family includes TI2V-5B and A14B T2V/I2V variants; TI2V-5B supports 720p at 24 FPS according to the repository.
- The 5B variant is the first candidate to benchmark on a GPU worker. Do not assume it runs at production quality on a 4 GB card.
- A14B is a large-worker-only tier; do not place it in a free notebook default.
- Model weights and inference code must be checked separately for licence and redistribution terms.

### LTX-2.5

- Official repository: https://github.com/Lightricks/LTX-2
- The repository describes a 22B audio/video model. It recommends distilled pipeline for speed, FP8 casting and CPU/disk offload for constrained memory.
- The code is Apache-2.0, but LTX model weights are governed by the separate LTX-2.x Community License. Never label the weights Apache-2.0.
- Treat it as a high-memory evaluation candidate, not a default for this user's hardware.

### HunyuanVideo

- Official repository: https://github.com/Tencent-Hunyuan/HunyuanVideo
- Evaluate only after verifying current version, hardware and region/commercial terms for the exact model weights.
- Large model; not a free default for this project.

### Smaller / alternative models

- CogVideoX small variants, Wan2.1 1.3B and other compact models may be useful in constrained workflows, but published low-memory numbers often rely on aggressive offload, low resolution, quantization or community wrappers. A model is production-eligible only after a reproducible benchmark on the actual worker.
- Do not assume that "open weights", "open source code", "free download" and "commercially usable" mean the same thing.

## Licence decision gates

For every model record separately:
1. Repository code licence and SPDX identifier.
2. Exact model-weight licence URL and version/date.
3. Training dataset and output restrictions if published.
4. Territory, revenue, user-count and acceptable-use restrictions.
5. Commercial use eligibility for the intended business.
6. Whether a fine-tune, LoRA, quantized copy or redistribution changes obligations.

A permissive code licence does not override model-weight terms. Store evidence URLs and review dates. If licence is unknown, block commercial generation rather than guessing.

## What the pipeline should do

1. Determine actual host capability from runtime probes, not a hard-coded workstation profile.
2. If no supported GPU exists, skip local diffusion. Use existing video, stills, motion design and narration.
3. If a compatible worker is online, ask its capability endpoint for free VRAM, supported model IDs, queue depth and max clip size.
4. Admit only jobs that fit the worker's declared limits with a safety margin.
5. Pin model revision, workflow JSON hash, custom node revisions and checkpoint hashes.
6. Cache outputs by prompt, seed, model revision, dimensions, workflow hash and source image hash.
7. Set a per-job time/attempt budget. On timeout or OOM, retry once at a smaller profile, then use the editorial fallback.
8. Never hold GitHub Actions open while waiting indefinitely for a notebook GPU.

## Benchmark protocol

Every candidate must render the same three-shot suite:
- Human / face close-up with controlled movement.
- Product / object motion with readable details.
- Wide environmental scene with camera movement.

Record:
- Exact model revision and weight licence.
- GPU model, VRAM total/free, driver, CUDA/ROCm, ComfyUI and node versions.
- Resolution, frame count, FPS, steps, quantization and offload flags.
- Queue wait, inference seconds, peak VRAM/RAM, failure rate and output bytes.
- Human-rated prompt adherence, anatomy, temporal consistency, motion artefacts and editability.
- Total cash cost and free-quota usage.

Do not compare a 480p 4-second clip to a 720p 8-second clip as if the quality/cost were equivalent.

## Recommended route for Cinema Studio

- Default: Wikimedia Commons / Internet Archive / other explicitly licensed source media + generated stills + Remotion/FFmpeg motion.
- Optional GPU: ComfyUI worker with a small, pinned model profile; Wan2.2 TI2V-5B is a candidate only after benchmark.
- Advanced GPU: LTX-2.5 and Wan A14B only on hardware that meets verified requirements and exact licence terms.
- Research-only: evaluate new models through the same benchmark harness before adding them to production.

## Primary references

- Kaggle notebooks: https://www.kaggle.com/docs/notebooks
- Kaggle GPU tips: https://www.kaggle.com/page/GPU-tips-and-tricks
- Google Colab FAQ: https://research.google.com/colaboratory/faq.html
- Wan 2.2: https://github.com/Wan-Video/Wan2.2
- LTX-2: https://github.com/Lightricks/LTX-2
- Dagu: https://github.com/dagucloud/dagu
- AI Video Studio reference architecture: https://github.com/06pratyush/ai-video-pipeline

The reference AI Video Studio project is useful for studying a durable SQLite queue, VRAM-aware lifecycle, model catalog, local ComfyUI, Kokoro, Whisper, RIFE and FFmpeg integration. It is not automatically compatible with this repository; inspect its code, dependencies and licences before copying components.
