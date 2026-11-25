---
name: cinema-autonomous-video-studio
description: Master skill integrating official remotion-dev/skills rules, Three.js WebGL scenes, Ken Burns B-roll cinematography, procedural FFmpeg ambient scoring, and edge-tts word-boundary captions.
---

# Cinema Autonomous Video Studio Skill

## Installed & Integrated Capabilities
- **Official Remotion Agent Skills (`remotion-dev/skills`)**: Installed automatically via `npx skills add remotion-dev/skills` during setup/CI.
- **Cinematography Engine (`src/components/CinemaBackdrop.tsx`)**: Drives `<OffthreadVideo>` and `<Img>` with deterministic Ken Burns camera rigs (`zoom_in`, `zoom_out`, `pan_left`, `pan_right`, `dolly_push`), `@remotion/noise` organic camera drift, anamorphic lens flares, floating volumetric particles, and 2.39:1 cinema letterbox bars.
- **Audio & SFX Architecture (`src/MainVideo.tsx` & `scripts/generate_assets.py`)**: Layers `edge-tts` neural voiceover, FFmpeg-synthesized sub-bass atmospheric score (`public/ambient_score.mp3`), and `@remotion/sfx` (`whoosh`, `whip`, `ding`) transitions.
