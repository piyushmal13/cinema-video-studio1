import React from 'react';
import {
  AbsoluteFill,
  Audio,
  Sequence,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from 'remotion';
import rawVideoData from '../public/video_data.json';
import { CinemaBackdrop } from './components/CinemaBackdrop';
import { ThreeDScenes } from './components/ThreeDScenes';
import { VideoProps, SceneItem } from './types';

const videoData = rawVideoData as VideoProps;

const SubtitleOverlay: React.FC<{
  words: VideoProps['words'];
  themeColor: string;
}> = ({ words, themeColor }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const currentSec = frame / fps;

  if (!words || words.length === 0) return null;

  const activeIndex = words.findIndex(
    (w) => currentSec >= w.start - 0.08 && currentSec <= w.end + 0.15
  );

  if (activeIndex === -1) return null;

  const windowStart = Math.max(0, activeIndex - 2);
  const windowEnd = Math.min(words.length, activeIndex + 3);
  const visibleWords = words.slice(windowStart, windowEnd);

  return (
    <div
      style={{
        position: 'absolute',
        bottom: '11%',
        left: '6%',
        right: '6%',
        display: 'flex',
        flexWrap: 'wrap',
        justifyContent: 'center',
        gap: '10px',
        zIndex: 30,
        pointerEvents: 'none',
      }}
    >
      {visibleWords.map((item, idx) => {
        const isCurrent = windowStart + idx === activeIndex;
        return (
          <span
            key={`${item.word}-${windowStart + idx}`}
            style={{
              fontFamily: 'system-ui, -apple-system, BlinkMacSystemFont, sans-serif',
              fontSize: isCurrent ? 44 : 38,
              fontWeight: 900,
              letterSpacing: '0.02em',
              textTransform: 'uppercase',
              color: isCurrent ? themeColor : '#F8FAFC',
              backgroundColor: 'rgba(5, 8, 15, 0.78)',
              padding: '6px 14px',
              borderRadius: '10px',
              border: isCurrent ? `1px solid ${themeColor}` : '1px solid rgba(255,255,255,0.12)',
              boxShadow: isCurrent ? `0 0 24px ${themeColor}55` : '0 4px 16px rgba(0,0,0,0.6)',
              transform: isCurrent ? 'scale(1.06)' : 'scale(1)',
            }}
          >
            {item.word}
          </span>
        );
      })}
    </div>
  );
};

const SceneCardOverlay: React.FC<{
  scene: SceneItem;
  themeColor: string;
}> = ({ scene, themeColor }) => {
  const frame = useCurrentFrame();
  const opacity = Math.min(1, frame / 12);
  const translateY = Math.max(0, 18 - frame * 1.5);

  return (
    <AbsoluteFill
      style={{
        justifyContent: 'space-between',
        padding: '64px 48px',
        opacity,
        transform: `translateY(${translateY}px)`,
        zIndex: 20,
        pointerEvents: 'none',
      }}
    >
      <div>
        {scene.kicker && (
          <div
            style={{
              display: 'inline-block',
              fontFamily: 'monospace',
              fontSize: 20,
              fontWeight: 700,
              letterSpacing: '0.18em',
              color: themeColor,
              backgroundColor: 'rgba(5, 8, 15, 0.82)',
              border: `1px solid ${themeColor}66`,
              padding: '8px 16px',
              borderRadius: '999px',
              marginBottom: '18px',
            }}
          >
            {scene.kicker}
          </div>
        )}

        <h1
          style={{
            fontFamily: 'system-ui, -apple-system, BlinkMacSystemFont, sans-serif',
            fontSize: 54,
            fontWeight: 900,
            lineHeight: 1.12,
            color: '#FFFFFF',
            margin: 0,
            textShadow: '0 6px 28px rgba(0, 0, 0, 0.85)',
          }}
        >
          {scene.headline}
        </h1>

        {scene.subline && (
          <p
            style={{
              fontFamily: 'system-ui, -apple-system, BlinkMacSystemFont, sans-serif',
              fontSize: 28,
              fontWeight: 500,
              color: '#CBD5E1',
              marginTop: '14px',
              textShadow: '0 4px 18px rgba(0, 0, 0, 0.85)',
            }}
          >
            {scene.subline}
          </p>
        )}

        {scene.type === 'split_compare' && (
          <div
            style={{
              display: 'flex',
              gap: '20px',
              marginTop: '36px',
            }}
          >
            <div
              style={{
                flex: 1,
                backgroundColor: 'rgba(15, 23, 42, 0.86)',
                border: '1px solid rgba(248, 113, 113, 0.45)',
                borderRadius: '16px',
                padding: '24px',
              }}
            >
              <div style={{ color: '#F87171', fontSize: 18, fontWeight: 800, marginBottom: 8 }}>
                LEGACY
              </div>
              <div style={{ color: '#F1F5F9', fontSize: 26, fontWeight: 700 }}>
                {scene.leftLabel || 'Manual Execution'}
              </div>
            </div>

            <div
              style={{
                flex: 1,
                backgroundColor: 'rgba(15, 23, 42, 0.86)',
                border: `1px solid ${themeColor}`,
                borderRadius: '16px',
                padding: '24px',
              }}
            >
              <div style={{ color: themeColor, fontSize: 18, fontWeight: 800, marginBottom: 8 }}>
                NEXT-GEN
              </div>
              <div style={{ color: '#FFFFFF', fontSize: 26, fontWeight: 700 }}>
                {scene.rightLabel || 'Autonomous AI'}
              </div>
            </div>
          </div>
        )}
      </div>
    </AbsoluteFill>
  );
};

export const MainVideo: React.FC = () => {
  const { fps } = useVideoConfig();
  const themeColor = videoData.themeColor || '#D4AF37';
  const scenes = videoData.scenes || [];

  return (
    <AbsoluteFill style={{ backgroundColor: '#05080F' }}>
      {videoData.voiceoverFile && (
        <Audio src={staticFile(videoData.voiceoverFile)} volume={1} />
      )}
      {videoData.ambientScoreFile && (
        <Audio src={staticFile(videoData.ambientScoreFile)} volume={0.4} />
      )}

      {scenes.map((scene, index) => {
        const fromFrame = Math.max(0, Math.round(scene.startSec * fps));
        const durationFrames = Math.max(
          15,
          Math.round((scene.endSec - scene.startSec) * fps)
        );
        const cleanMedia = (scene.mediaFile || '').replace(/^\/?public\//, '');

        return (
          <Sequence
            key={`scene-${index}`}
            from={fromFrame}
            durationInFrames={durationFrames}
          >
            <AbsoluteFill>
              <CinemaBackdrop
                mediaFile={cleanMedia}
                mediaKind={scene.mediaKind}
                cameraMotion={scene.cameraMotion}
                accentColor={themeColor}
              />
              <ThreeDScenes
                sceneType={scene.type}
                themeColor={themeColor}
                barValues={scene.barValues}
              />
              <SceneCardOverlay scene={scene} themeColor={themeColor} />
            </AbsoluteFill>
          </Sequence>
        );
      })}

      <div
        style={{
          position: 'absolute',
          top: 28,
          right: 36,
          fontFamily: 'monospace',
          fontSize: 18,
          fontWeight: 800,
          letterSpacing: '0.16em',
          color: themeColor,
          backgroundColor: 'rgba(5, 8, 15, 0.72)',
          padding: '6px 14px',
          borderRadius: '8px',
          border: `1px solid ${themeColor}44`,
          zIndex: 40,
        }}
      >
        {videoData.brandTag || 'IFXTRADES'}
      </div>

      <SubtitleOverlay words={videoData.words || []} themeColor={themeColor} />
    </AbsoluteFill>
  );
};
