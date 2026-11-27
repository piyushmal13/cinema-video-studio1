# Free / Open-Source AI Stack

This project integrates six external open-source repositories through small adapters. It does **not** copy all six upstream codebases or model weights into this repository. The integration boundaries keep the Telegram bot, Cloudflare Worker, GitHub Actions, Python director and Remotion renderer maintainable while allowing the upstream projects to be updated independently.

| Upstream repository | Role in this project | Integration status | License notes |
|---|---|---|---|
| [ollama/ollama](https://github.com/ollama/ollama) | Local LLM brain for script/storyboard generation | Implemented through the Ollama /api/chat endpoint in scripts/generate_assets.py; set OLLAMA_BASE_URL and OLLAMA_MODEL | Ollama source is MIT; each model has its own licence and acceptable-use terms |
| [Comfy-Org/ComfyUI](https://github.com/Comfy-Org/ComfyUI) | Local / Colab-hosted image and video generation workflows | Implemented through scripts/comfyui_client.py; set the ComfyUI URL, API workflow JSON and optional node mapping | ComfyUI is GPL-3.0; workflow nodes and model checkpoints have separate licences |
| [Wan-Video/Wan2.1](https://github.com/Wan-Video/Wan2.1) | Actual generated motion clips on a GPU worker | Existing notebooks/Kling_Class_GPU_Worker.ipynb uses the Wan 2.1 1.3B Diffusers pipeline; the main director chooses varied scenes and assigns per-job seeds | Upstream project and the cited Wan model release are Apache-2.0; check the specific checkpoint and any third-party LoRA separately |
| [m-bain/whisperX](https://github.com/m-bain/whisperX) | Word-level forced alignment for captions and narration timing | Implemented as the optional scripts/speech_alignment.py route; enable with WHISPERX_ENABLED=1 and install requirements-optional.txt on the worker | WhisperX source is BSD-2-Clause; ASR / alignment model weights and their terms are separate |
| [AcademySoftwareFoundation/OpenTimelineIO](https://github.com/AcademySoftwareFoundation/OpenTimelineIO) | Portable editorial timeline for handoff to NLE tools | Implemented in scripts/timeline_export.py; enable with OTIO_EXPORT_ENABLED=1 | Apache-2.0 |
| [thewh1teagle/kokoro-onnx](https://github.com/thewh1teagle/kokoro-onnx) | Local ONNX text-to-speech, including Hindi and English voice options | Implemented in scripts/kokoro_tts.py; install optional dependencies, provide local model/voice files and set KOKORO_TTS_ENABLED=1 | ONNX wrapper is MIT; Kokoro model is Apache-2.0; individual voice training-data quality/licensing should be checked before commercial voice selection |

## How provider routing works

1. **Creative brain:** when a reachable Ollama server is configured, it is tried first. Otherwise the configured Gemini API is used when enabled, followed by the keyless Pollinations text endpoint. If these fail or return invalid output, the director produces a topic-specific degraded storyboard and marks it in video_data.json.
2. **Visual generation:** ComfyUI is tried only when a compatible workflow is configured. The existing Wan notebook replaces the generated-video callback with its local Wan worker. In GitHub Actions, the existing keyless video providers and public-domain / CC0 footage fallbacks remain available.
3. **Voice:** optional local Kokoro is attempted only when enabled and its model/voice files exist. Otherwise Edge TTS runs, followed by gTTS. WhisperX can replace estimated word timings after speech generation.
4. **Editorial delivery:** the renderer writes its Remotion MP4, then render QA checks that audio and video streams exist and duration is plausible. OpenTimelineIO can export the edit plan. The post-production step creates captions, hashtags, a cover frame and a publishing record before Telegram delivery.

## Configuration

### Ollama
Set OLLAMA_BASE_URL to a server reachable from the runner, and OLLAMA_MODEL to an already-downloaded model. A private Tailscale endpoint is suitable when the runner can reach it. This project does not pull a multi-gigabyte model on every GitHub Actions run.

### ComfyUI
Set COMFYUI_BASE_URL, COMFYUI_IMAGE_WORKFLOW and/or COMFYUI_VIDEO_WORKFLOW. Workflow JSON must use the ComfyUI API prompt format. For custom graphs, set COMFYUI_IMAGE_MAPPING / COMFYUI_VIDEO_MAPPING to JSON files listing positive_prompt_nodes, optional negative_prompt_nodes, and seed_nodes. The workflow's custom nodes and checkpoints must already be installed on the ComfyUI host.

### Wan 2.1
Open the notebook in a GPU-enabled Colab/Kaggle runtime and run its cells in order. It prompts for the Telegram bot token at runtime and refuses to start if that bot has an active webhook. Use a separate polling bot when Cloudflare webhook delivery must remain active. The notebook uses Wan 2.1 1.3B and keeps the existing sequential polling design.

### WhisperX
Install requirements-optional.txt in the GPU/CPU worker where alignment is required; set WHISPERX_ENABLED=1. Model downloads, GPU availability and inference time depend on the host. If the optional alignment step fails, the TTS-provided or estimated timings remain available.

### OpenTimelineIO
Install opentimelineio from requirements-optional.txt and set OTIO_EXPORT_ENABLED=1. The .otio file points to media files; it does not contain the rendered video or audio.

### Kokoro ONNX
Install requirements-optional.txt, then obtain the ONNX model and voice pack from their upstream release and put them on the worker. Set:
- KOKORO_TTS_ENABLED=1
- KOKORO_MODEL_PATH (default models/kokoro-v1.0.onnx)
- KOKORO_VOICES_PATH (default models/voices-v1.0.bin)
- KOKORO_HI_VOICE (default hf_alpha)
- KOKORO_EN_VOICE (default af_heart)
- KOKORO_SPEED (default 1.0)

Kokoro is an explicit opt-in local provider. If the model, voice pack, package or conversion tool is missing, the pipeline falls back to Edge TTS and gTTS instead of failing the whole render.

## Free does not mean unlimited

These repositories and their source code can be used without a paid API subscription under their respective licences, but execution still needs compute, storage, bandwidth and sometimes large model files. Colab/Kaggle GPU quotas, GitHub Actions included minutes, public inference endpoints and third-party media hosts are not guaranteed unlimited services. Model weights, custom ComfyUI nodes, LoRAs, TTS voices and datasets can have licences different from the code repository. Review the exact model and asset terms before commercial deployment.
