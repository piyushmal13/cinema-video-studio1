import React from 'react';
import {
  AbsoluteFill,
  Img,
  Loop,
  OffthreadVideo,
  interpolate,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from 'remotion';
import { noise2D } from '@remotion/noise';
import type { CameraMotion, SceneType, VisualTreatment } from '../types';

const sceneAccentColors: Record<SceneType, string> = {
  cinema_hero: '#D4AF37',
  three_d_globe: '#38BDF8',
  three_d_bars: '#A78BFA',
  candlestick_chart: '#34D399',
  split_compare: '#FB7185',
  step_list: '#22D3EE',
  cinema_outro: '#FBBF24',
  kinetic_type: '#E2E8F0',
  process_diagram: '#22C55E',
  editorial_montage: '#94A3B8',
  data_viz: '#60A5FA',
};

const LIGHT_TREATMENTS = new Set<VisualTreatment>([
  'documentary_lower_third', 'photo_essay', 'immersive_photo',
]);
const SIDE_TREATMENTS = new Set<VisualTreatment>([
  'editorial_split', 'cinematic_side_caption',
]);
const GRAPHIC_TREATMENTS = new Set<VisualTreatment>([
  'process_blueprint', 'data_stage', 'market_chart', 'vertical_timeline',
]);

export const CinemaBackdrop: React.FC<{
  mediaFile?: string;
  mediaFiles?: string[];
  mediaKind?: 'video' | 'image' | 'none';
  cameraMotion?: CameraMotion;
  sceneType?: SceneType;
  visualTreatment?: VisualTreatment;
  sceneIndex?: number;
  motionDurationInFrames?: number;
  beatSync?: boolean;
  beatTimestamps?: number[];
  accentColor: string;
  isCinemaMode?: boolean;
}> = ({
  mediaFile,
  mediaFiles = [],
  mediaKind = 'none',
  cameraMotion = 'zoom_in',
  sceneType,
  visualTreatment = 'documentary_lower_third',
  sceneIndex = 0,
  motionDurationInFrames,
  beatSync = false,
  beatTimestamps = [],
  accentColor,
  isCinemaMode = false,
}) => {
  const frame = useCurrentFrame();
  const { durationInFrames, fps, width, height } = useVideoConfig();
  const totalMotionFrames = Math.max(1, motionDurationInFrames ?? durationInFrames);
  const progress = Math.min(1, Math.max(0, frame / totalMotionFrames));
  const backdropAccent = sceneType ? sceneAccentColors[sceneType] : accentColor;

  let scale = 1.035;
  let translateX = 0;
  let translateY = 0;
  switch (cameraMotion) {
    case 'zoom_in':
      scale = interpolate(progress, [0, 1], [1.015, 1.17]);
      break;
    case 'zoom_out':
      scale = interpolate(progress, [0, 1], [1.18, 1.025]);
      break;
    case 'pan_left':
      scale = 1.14;
      translateX = interpolate(progress, [0, 1], [width * 0.035, -width * 0.035]);
      break;
    case 'pan_right':
      scale = 1.14;
      translateX = interpolate(progress, [0, 1], [-width * 0.035, width * 0.035]);
      break;
    case 'dolly_push':
      scale = interpolate(progress, [0, 1], [1.0, 1.23]);
      translateY = interpolate(progress, [0, 1], [height * 0.012, -height * 0.018]);
      break;
    case 'tilt_up':
      scale = 1.12;
      translateY = interpolate(progress, [0, 1], [height * 0.035, -height * 0.035]);
      break;
    case 'tilt_down':
      scale = 1.12;
      translateY = interpolate(progress, [0, 1], [-height * 0.035, height * 0.035]);
      break;
    case 'drift_diagonal':
      scale = 1.16;
      translateX = interpolate(progress, [0, 1], [-width * 0.025, width * 0.025]);
      translateY = interpolate(progress, [0, 1], [height * 0.02, -height * 0.02]);
      break;
    case 'handheld':
      scale = 1.12;
      translateX = interpolate(progress, [0, 1], [width * 0.012, -width * 0.012]);
      translateY = interpolate(progress, [0, 1], [-height * 0.008, height * 0.008]);
      break;
    case 'static':
      scale = 1.015;
      break;
  }

  const handheld = cameraMotion === 'handheld';
  const shakeX = handheld ? noise2D('handheld-x', frame / (fps * 0.45), sceneIndex) * 2.2 : 0;
  const shakeY = handheld ? noise2D('handheld-y', sceneIndex, frame / (fps * 0.45)) * 2.2 : 0;

  let beatPulse = 0;
  if (beatSync && beatTimestamps.length > 0) {
    const currentSec = frame / fps;
    let low = 0;
    let high = beatTimestamps.length;
    while (low < high) {
      const middle = Math.floor((low + high) / 2);
      if (beatTimestamps[middle] < currentSec) low = middle + 1;
      else high = middle;
    }
    const nearestBeat = Math.min(
      beatTimestamps[low] ?? Number.POSITIVE_INFINITY,
      beatTimestamps[low - 1] ?? Number.POSITIVE_INFINITY,
    );
    beatPulse = Math.max(0, 1 - Math.abs(nearestBeat - currentSec) / 0.12) * 0.012;
  }
  const animatedScale = scale * (1 + beatPulse);
  const mediaTransform = `scale(${animatedScale}) translate(${translateX + shakeX}px, ${translateY + shakeY}px)`;

  const sequenceFiles = mediaFiles.filter((file) => typeof file === 'string' && file.length > 0);
  const imageFiles = sequenceFiles.length ? sequenceFiles : (mediaFile ? [mediaFile] : []);
  const slot = Math.min(imageFiles.length - 1, Math.floor(progress * imageFiles.length));
  const activeImage = imageFiles.length > 0 ? imageFiles[Math.max(0, slot)] : '';
  const previousImage = imageFiles.length > 1 && slot > 0 ? imageFiles[slot - 1] : '';
  const localProgress = imageFiles.length > 1 ? (progress * imageFiles.length) - slot : 1;
  const imageFade = slot === 0 ? 1 : interpolate(localProgress, [0, 0.16], [0, 1], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
  });

  const fallbackBackground = GRAPHIC_TREATMENTS.has(visualTreatment)
    ? `linear-gradient(90deg,${backdropAccent}1c 1px,transparent 1px),linear-gradient(${backdropAccent}1c 1px,transparent 1px),radial-gradient(ellipse at 65% 42%,${backdropAccent}25, #05080e 66%)`
    : visualTreatment === 'comparative_split'
      ? 'linear-gradient(105deg,rgba(127,29,29,0.42),rgba(4,8,14,0.9) 49%,rgba(34,197,94,0.22)),#05080e'
      : `radial-gradient(ellipse at 58% 42%, ${backdropAccent}34 0%, #101722 42%, #04060a 100%)`;

  const scrim = LIGHT_TREATMENTS.has(visualTreatment)
    ? 'linear-gradient(0deg,rgba(2,5,9,0.76) 0%,rgba(2,5,9,0.18) 37%,rgba(2,5,9,0.02) 68%)'
    : SIDE_TREATMENTS.has(visualTreatment)
      ? (visualTreatment === 'editorial_split'
        ? 'linear-gradient(90deg,rgba(2,5,9,0.85) 0%,rgba(2,5,9,0.53) 48%,rgba(2,5,9,0.05) 83%)'
        : 'linear-gradient(270deg,rgba(2,5,9,0.88) 0%,rgba(2,5,9,0.50) 43%,rgba(2,5,9,0.04) 82%)')
      : visualTreatment === 'kinetic_typography' || visualTreatment === 'cinema_end_frame'
        ? 'radial-gradient(ellipse at center,rgba(2,5,9,0.18),rgba(2,5,9,0.58) 92%)'
        : 'linear-gradient(180deg,rgba(2,5,9,0.22) 0%,rgba(2,5,9,0.05) 34%,rgba(2,5,9,0.78) 100%)';

  const photoFilter = LIGHT_TREATMENTS.has(visualTreatment)
    ? 'saturate(1.08) contrast(1.04) brightness(0.98)'
    : 'saturate(1.14) contrast(1.10) brightness(0.9)';

  return (
    <AbsoluteFill style={{ overflow: 'hidden', background: '#05070B' }}>
      {mediaFile && mediaKind === 'video' && (
        <AbsoluteFill style={{ transform: mediaTransform }}>
          <Loop durationInFrames={totalMotionFrames}>
            <OffthreadVideo
              src={staticFile(mediaFile)}
              muted
              style={{ width: '100%', height: '100%', objectFit: 'cover', filter: photoFilter }}
            />
          </Loop>
        </AbsoluteFill>
      )}

      {mediaKind === 'image' && activeImage && (
        <AbsoluteFill style={{ transform: mediaTransform }}>
          {previousImage && (
            <Img
              src={staticFile(previousImage)}
              style={{ width: '100%', height: '100%', objectFit: 'cover', filter: photoFilter }}
            />
          )}
          <Img
            src={staticFile(activeImage)}
            style={{
              width: '100%', height: '100%', objectFit: 'cover',
              filter: photoFilter, opacity: imageFade,
            }}
          />
        </AbsoluteFill>
      )}

      {(!mediaFile || mediaKind === 'none') && (
        <AbsoluteFill style={{
          background: fallbackBackground,
          backgroundSize: GRAPHIC_TREATMENTS.has(visualTreatment) ? '58px 58px,58px 58px,cover' : 'cover',
          transform: mediaTransform,
        }} />
      )}

      <AbsoluteFill style={{ background: scrim }} />

      {(visualTreatment === 'process_blueprint' || visualTreatment === 'data_stage' || visualTreatment === 'market_chart') && (
        <AbsoluteFill style={{
          opacity: 0.18,
          backgroundImage: 'linear-gradient(rgba(255,255,255,0.10) 1px,transparent 1px),linear-gradient(90deg,rgba(255,255,255,0.10) 1px,transparent 1px)',
          backgroundSize: '42px 42px',
          maskImage: 'linear-gradient(90deg,transparent,black 28%,black 88%,transparent)',
        }} />
      )}

      {(visualTreatment === 'editorial_cover' || visualTreatment === 'cinema_end_frame') && (
        <AbsoluteFill style={{
          border: '1px solid rgba(255,255,255,0.12)',
          margin: '3.5%',
          pointerEvents: 'none',
          opacity: 0.8,
        }} />
      )}

      {isCinemaMode && (
        <>
          <div style={{ position: 'absolute', top: 0, left: 0, right: 0, height: 54, background: '#000', zIndex: 40 }} />
          <div style={{ position: 'absolute', bottom: 0, left: 0, right: 0, height: 54, background: '#000', zIndex: 40 }} />
        </>
      )}
    </AbsoluteFill>
  );
};
