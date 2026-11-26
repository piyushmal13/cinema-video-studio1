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
import { CameraMotion, SceneType } from '../types';

const sceneAccentColors: Record<SceneType, string> = {
  cinema_hero: '#D4AF37',
  three_d_globe: '#38BDF8',
  three_d_bars: '#A78BFA',
  candlestick_chart: '#34D399',
  split_compare: '#FB7185',
  step_list: '#22D3EE',
  cinema_outro: '#FBBF24',
};

export const CinemaBackdrop: React.FC<{
  mediaFile?: string;
  mediaKind?: 'video' | 'image' | 'none';
  cameraMotion?: CameraMotion;
  sceneType?: SceneType;
  motionDurationInFrames?: number;
  beatSync?: boolean;
  beatTimestamps?: number[];
  accentColor: string;
  isCinemaMode?: boolean;
}> = ({
  mediaFile,
  mediaKind = 'none',
  cameraMotion = 'zoom_in',
  sceneType,
  motionDurationInFrames,
  beatSync = false,
  beatTimestamps = [],
  accentColor,
  isCinemaMode = false,
}) => {
  const frame = useCurrentFrame();
  const { durationInFrames, fps } = useVideoConfig();
  const progress = Math.min(
    1,
    frame / Math.max(1, motionDurationInFrames ?? durationInFrames)
  );
  const backdropAccent = sceneType ? sceneAccentColors[sceneType] : accentColor;

  let scale = 1.06;
  let translateX = 0;
  let translateY = 0;

  switch (cameraMotion) {
    case 'zoom_in':
      scale = interpolate(progress, [0, 1], [1.02, 1.18]);
      break;
    case 'zoom_out':
      scale = interpolate(progress, [0, 1], [1.2, 1.03]);
      break;
    case 'pan_left':
      scale = 1.14;
      translateX = interpolate(progress, [0, 1], [35, -35]);
      break;
    case 'pan_right':
      scale = 1.14;
      translateX = interpolate(progress, [0, 1], [-35, 35]);
      break;
    case 'dolly_push':
      scale = interpolate(progress, [0, 1], [1.0, 1.24]);
      translateY = interpolate(progress, [0, 1], [15, -20]);
      break;
  }

  const shakeX = noise2D('camX', frame / (fps * 2.5), 0) * 6;
  const shakeY = noise2D('camY', 0, frame / (fps * 2.5)) * 6;
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
      beatTimestamps[low - 1] ?? Number.POSITIVE_INFINITY
    );
    beatPulse = Math.max(0, 1 - Math.abs(nearestBeat - currentSec) / 0.12) * 0.018;
  } else if (beatSync) {
    beatPulse = Math.max(0, Math.sin((frame / fps) * Math.PI * 4)) * 0.012;
  }
  const animatedScale = scale * (1 + beatPulse);

  return (
    <AbsoluteFill style={{ overflow: 'hidden', backgroundColor: '#05070B' }}>
      {mediaFile && mediaKind === 'video' && (
        <AbsoluteFill
          style={{
            transform: `scale(${animatedScale}) translate(${translateX + shakeX}px, ${translateY + shakeY}px)`,
          }}
        >
          <Loop durationInFrames={motionDurationInFrames ?? durationInFrames}>
            <OffthreadVideo
              src={staticFile(mediaFile)}
              muted
              style={{ width: '100%', height: '100%', objectFit: 'cover', filter: 'contrast(1.12) saturate(1.15)' }}
            />
          </Loop>
        </AbsoluteFill>
      )}

      {mediaFile && mediaKind === 'image' && (
        <AbsoluteFill
          style={{
            transform: `scale(${animatedScale}) translate(${translateX + shakeX}px, ${translateY + shakeY}px)`,
          }}
        >
          <Img
            src={staticFile(mediaFile)}
            style={{ width: '100%', height: '100%', objectFit: 'cover', filter: 'contrast(1.15) saturate(1.18)' }}
          />
        </AbsoluteFill>
      )}

      {(!mediaFile || mediaKind === 'none') && (
        <AbsoluteFill
          style={{
            background: `radial-gradient(circle at 50% 35%, ${backdropAccent}42 0%, #090D16 55%, #04060A 100%), linear-gradient(135deg, #05070B 0%, ${backdropAccent}18 50%, #05070B 100%)`,
            transform: `scale(${animatedScale}) translate(${translateX + shakeX}px, ${translateY + shakeY}px)`,
          }}
        />
      )}

      <AbsoluteFill
        style={{
          zIndex: 5,
          pointerEvents: 'none',
          opacity: 0.22,
          mixBlendMode: 'soft-light',
          backgroundImage:
            'repeating-linear-gradient(0deg, rgba(255,255,255,0.035) 0px, transparent 1px, transparent 4px)',
          backgroundPositionY: `${frame % 4}px`,
        }}
      />

      <AbsoluteFill
        style={{
          background:
            'linear-gradient(180deg, rgba(4,6,10,0.78) 0%, rgba(4,6,10,0.38) 42%, rgba(4,6,10,0.88) 84%, rgba(4,6,10,0.97) 100%)',
        }}
      />

      <div
        style={{
          position: 'absolute',
          top: '22%',
          left: '-10%',
          right: '-10%',
          height: 2,
          background: `linear-gradient(90deg, transparent 0%, ${accentColor}55 50%, transparent 100%)`,
          filter: 'blur(3px)',
          opacity: 0.65,
        }}
      />

      <AbsoluteFill style={{ pointerEvents: 'none' }}>
        {Array.from({ length: 14 }).map((_, idx) => {
          const px = (idx * 173 + frame * (0.4 + (idx % 3) * 0.2)) % 1080;
          const py = (idx * 293 - frame * (0.5 + (idx % 4) * 0.15) + 4000) % 1920;
          const size = 2 + (idx % 3) * 2;
          return (
            <div
              key={idx}
              style={{
                position: 'absolute',
                left: px,
                top: py,
                width: size,
                height: size,
                borderRadius: '50%',
                backgroundColor: idx % 2 === 0 ? accentColor : '#38BDF8',
                opacity: 0.25 + (idx % 4) * 0.08,
                boxShadow: `0 0 8px ${accentColor}`,
              }}
            />
          );
        })}
      </AbsoluteFill>

      {isCinemaMode && (
        <>
          <div style={{ position: 'absolute', top: 0, left: 0, right: 0, height: 84, backgroundColor: '#000000', zIndex: 40 }} />
          <div style={{ position: 'absolute', bottom: 0, left: 0, right: 0, height: 84, backgroundColor: '#000000', zIndex: 40 }} />
        </>
      )}
    </AbsoluteFill>
  );
};
