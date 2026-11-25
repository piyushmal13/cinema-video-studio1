#!/usr/bin/env bash
set -e
echo "1/3 Installing Remotion, Three.js, React Three Fiber, Transitions, Shapes, Noise & SFX..."
npm install
echo "2/3 Installing Official Remotion Agent Skills from GitHub (remotion-dev/skills)..."
npx skills add remotion-dev/skills -y || npx remotion skills add || true
echo "3/3 Installing Python Neural Voiceover & Media Engine..."
pip install --upgrade edge-tts requests
echo "All engines and GitHub skills installed!"
