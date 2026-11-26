import React from 'react';
import {
  AbsoluteFill,
  Audio,
  interpolate,
  Sequence,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from 'remotion';
import { springTiming, TransitionSeries } from '@remotion/transitions';
import { fade } from '@remotion/transitions/fade';
import { slide } from '@remotion/transitions/slide';
import { wipe } from '@remotion/transitions/wipe';
import '@fontsource/montserrat/900.css';
import rawVideoData from '../public/video_data.json';
import { CinemaBackdrop } from './components/CinemaBackdrop';
import { ThreeDScenes } from './components/ThreeDScenes';
import { VideoProps, SceneItem } from './types';

const defaultVideoData = rawVideoData as VideoProps;

const SubtitleOverlay: React.FC<{
  words: VideoProps['words'];
  themeColor: string;
}> = ({ words, themeColor }) => {
  const frame = useCurrentFrame();
  const { fps, height } = useVideoConfig();
  const currentSec = frame / fps;

  if (!words || words.length === 0) return null;

  const activeIndex = words.findIndex(
    (w) => currentSec >= w.start - 0.08 && currentSec <= w.end + 0.15
  );

  if (activeIndex === -1) return null;

  const windowStart = activeIndex;
  const windowEnd = Math.min(words.length, activeIndex + 3);
  const visibleWords = words.slice(windowStart, windowEnd);
  const fontSize = Math.max(22, Math.min(44, height * 0.024));

  return (
    <div
      style={{
        position: 'absolute',
        bottom: '19%',
        left: '6%',
        right: '6%',
        display: 'flex',
        flexWrap: 'wrap',
        justifyContent: 'center',
        gap: '8px',
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
              fontFamily: '"Montserrat", system-ui, sans-serif',
              fontSize: isCurrent ? fontSize : fontSize * 0.86,
              fontWeight: 900,
              letterSpacing: '0.02em',
              textTransform: 'uppercase',
              color: isCurrent ? themeColor : '#F8FAFC',
              backgroundColor: 'rgba(5, 8, 15, 0.78)',
              padding: '5px 12px',
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
  const { fps, height } = useVideoConfig();
  const opacity = Math.min(1, frame / 12);
  const translateY = Math.max(0, 18 - frame * 1.5);
  const headlineSize = Math.max(44, Math.min(68, height * 0.035));
  const statProgress = spring({ frame, fps, config: { damping: 16, stiffness: 85 } });
  const statMatch = scene.statValue?.match(/^(.*?)(-?[\d,]+(?:\.\d+)?)(.*)$/);
  const animatedStat = statMatch
    ? `${statMatch[1]}${(
        Number(statMatch[2].replace(/,/g, '')) * statProgress
      ).toLocaleString('en-US', { maximumFractionDigits: 2 })}${statMatch[3]}`
    : scene.statValue;
  const shortLabel = (label: string) => label.toUpperCase();

  return (
    <AbsoluteFill
      style={{
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        boxSizing: 'border-box',
        padding: '16% 7% 25%',
        opacity,
        transform: `translateY(${translateY}px)`,
        zIndex: 20,
        pointerEvents: 'none',
      }}
    >
      <div
        style={{
          width: '100%',
          maxWidth: 960,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          textAlign: 'center',
          gap: 18,
          padding: '30px 28px',
          borderRadius: 28,
          border: '1px solid transparent',
          background: `linear-gradient(145deg, rgba(5,8,15,0.76), rgba(8,13,24,0.54)) padding-box, conic-gradient(from ${frame * 7}deg, ${themeColor}cc, transparent 24%, rgba(255,255,255,0.12) 48%, transparent 68%, ${themeColor}cc) border-box`,
          backgroundClip: 'padding-box, border-box',
          boxShadow: '0 24px 80px rgba(0,0,0,0.35)',
          backdropFilter: 'blur(10px)',
        }}
      >
        {scene.kicker && (
          <div
            style={{
              display: 'inline-block',
              fontFamily: '"JetBrains Mono", monospace',
              fontSize: Math.max(16, Math.min(21, height * 0.011)),
              fontWeight: 700,
              letterSpacing: '0.18em',
              color: themeColor,
              backgroundColor: 'rgba(5, 8, 15, 0.82)',
              border: `1px solid ${themeColor}66`,
              padding: '8px 16px',
              borderRadius: '999px',
            }}
          >
            {shortLabel(scene.kicker)}
          </div>
        )}

        <h1
          style={{
            fontFamily: '"Montserrat", "Arial Black", system-ui, sans-serif',
            fontSize: headlineSize,
            fontWeight: 900,
            lineHeight: 1.02,
            color: '#FFFFFF',
            margin: 0,
            textTransform: 'uppercase',
            textWrap: 'balance',
            textShadow: `0 0 34px ${themeColor}44, 0 6px 28px rgba(0,0,0,0.85)`,
          }}
        >
          {shortLabel(scene.headline)}
        </h1>

        {scene.subline && (
          <p
            style={{
              fontFamily: '"Inter", system-ui, sans-serif',
              fontSize: Math.max(22, Math.min(30, height * 0.016)),
              fontWeight: 500,
              color: '#CBD5E1',
              margin: 0,
              textShadow: '0 4px 18px rgba(0, 0, 0, 0.85)',
            }}
          >
            {scene.subline}
          </p>
        )}

        {scene.statValue && (
          <div
            style={{
              padding: '12px 30px',
              borderRadius: 18,
              border: `1px solid ${themeColor}99`,
              background: `${themeColor}20`,
              color: '#FFFFFF',
              fontFamily: '"Montserrat", "Arial Black", system-ui, sans-serif',
              fontSize: Math.max(38, Math.min(64, height * 0.034)),
              fontWeight: 900,
              textShadow: `0 0 28px ${themeColor}88`,
            }}
          >
            {animatedStat}
          </div>
        )}

        {scene.type === 'candlestick_chart' && <IllustrativeCandlestickChart themeColor={themeColor} />}

        {scene.type === 'split_compare' && (
          <div
            style={{
              display: 'flex',
              width: '100%',
              gap: 14,
            }}
          >
            <div
              style={{
                flex: 1,
                background: 'linear-gradient(140deg, rgba(127,29,29,0.68), rgba(15,23,42,0.82))',
                border: '1px solid rgba(248,113,113,0.62)',
                borderRadius: 18,
                padding: 18,
              }}
            >
              <div style={{ color: '#F87171', fontSize: 18, fontWeight: 800, marginBottom: 8, fontFamily: '"JetBrains Mono", monospace' }}>
                {shortLabel(scene.leftLabel || 'RETAIL TRAP')}
              </div>
              <div style={{ color: '#F1F5F9', fontSize: Math.max(20, Math.min(30, height * 0.016)), fontWeight: 800 }}>
                {scene.subline || 'Reactive decisions'}
              </div>
            </div>

            <div
              style={{
                flex: 1,
                background: `linear-gradient(140deg, ${themeColor}33, rgba(15,23,42,0.86))`,
                border: `1px solid ${themeColor}`,
                borderRadius: 18,
                padding: 18,
              }}
            >
              <div style={{ color: themeColor, fontSize: 18, fontWeight: 800, marginBottom: 8, fontFamily: '"JetBrains Mono", monospace' }}>
                {shortLabel(scene.rightLabel || 'INSTITUTIONAL EDGE')}
              </div>
              <div style={{ color: '#FFFFFF', fontSize: Math.max(20, Math.min(30, height * 0.016)), fontWeight: 800 }}>
                {scene.kicker || 'Disciplined execution'}
              </div>
            </div>
          </div>
        )}
      </div>
    </AbsoluteFill>
  );
};

const IllustrativeCandlestickChart: React.FC<{ themeColor: string }> = ({ themeColor }) => {
  const frame = useCurrentFrame();
  const candleCount = 18;
  const candles = Array.from({ length: candleCount }, (_, index) => {
    const trend = Math.sin(index * 0.61 + frame / 36) * 24;
    const wave = Math.sin(index * 1.7 + 0.4) * 22;
    const center = 134 - trend - wave;
    const body = 12 + Math.abs(Math.sin(index * 2.3)) * 18;
    return {
      x: 34 + index * 40,
      top: Math.max(42, center - body / 2),
      bottom: Math.min(210, center + body / 2),
      wickTop: Math.max(22, center - body),
      wickBottom: Math.min(230, center + body),
      up: Math.sin(index * 1.37 + frame / 60) > 0,
    };
  });

  return (
    <div style={{ width: '100%', maxWidth: 820, padding: '12px 14px 6px', borderRadius: 18, background: 'rgba(2,6,12,0.76)', border: '1px solid rgba(148,163,184,0.24)' }}>
      <div style={{ textAlign: 'left', color: '#CBD5E1', font: '700 14px "JetBrains Mono", monospace', letterSpacing: '0.08em' }}>
        XAUUSD · ILLUSTRATIVE PRICE ACTION
      </div>
      <svg viewBox="0 0 780 250" style={{ width: '100%', display: 'block' }} aria-label="Illustrative animated candlestick chart">
        <rect x="480" y="24" width="270" height="38" fill={`${themeColor}22`} stroke={`${themeColor}88`} strokeDasharray="5 6" />
        <text x="488" y="18" fill={themeColor} fontSize="11" fontFamily="monospace">LIQUIDITY SWEEP ZONE · ILLUSTRATIVE</text>
        {[80, 130, 180, 230].map((y) => <line key={y} x1="20" x2="760" y1={y} y2={y} stroke="rgba(148,163,184,0.18)" />)}
        {candles.map((candle, index) => {
          const color = candle.up ? '#34D399' : '#FB7185';
          return (
            <g key={index} opacity={0.78 + (index % 3) * 0.08}>
              <line x1={candle.x + 8} x2={candle.x + 8} y1={candle.wickTop} y2={candle.wickBottom} stroke={color} strokeWidth="2" />
              <rect x={candle.x} y={candle.top} width="16" height={Math.max(5, candle.bottom - candle.top)} fill={color} rx="2" />
            </g>
          );
        })}
      </svg>
    </div>
  );
};

const TransitionFlash: React.FC = () => {
  const frame = useCurrentFrame();
  const opacity = interpolate(frame, [0, 1, 4], [0, 0.2, 0], {
    extrapolateRight: 'clamp',
    extrapolateLeft: 'clamp',
  });
  const scale = interpolate(frame, [0, 4], [1.035, 1], {
    extrapolateRight: 'clamp',
    extrapolateLeft: 'clamp',
  });
  if (frame >= 4) return null;
  return (
    <AbsoluteFill
      style={{
        backgroundColor: '#FFFFFF',
        opacity,
        transform: `scale(${scale})`,
        mixBlendMode: 'screen',
        pointerEvents: 'none',
        zIndex: 35,
      }}
    />
  );
};

export const MainVideo: React.FC<VideoProps> = (props) => {
  const videoData = { ...defaultVideoData, ...props };
  const { fps } = useVideoConfig();
  const themeColor = videoData.themeColor || '#D4AF37';
  const scenes = videoData.scenes || [];
  const transitionFrames = scenes.length > 1 ? 8 : 0;
  const sceneDurations = scenes.map((scene) =>
    Math.max(15, Math.round((scene.endSec - scene.startSec) * fps))
  );
  const paddedDurations = sceneDurations.map(
    (duration, index) =>
      duration +
      (index > 0 ? Math.floor(transitionFrames / 2) : 0) +
      (index < scenes.length - 1 ? Math.ceil(transitionFrames / 2) : 0)
  );

  return (
    <AbsoluteFill style={{ backgroundColor: '#05080F' }}>
      {videoData.masterAudioFile && (
        <Audio src={staticFile(videoData.masterAudioFile)} volume={1} />
      )}
      {!videoData.masterAudioFile && videoData.voiceoverFile && (
        <Audio src={staticFile(videoData.voiceoverFile)} volume={1} />
      )}
      {!videoData.masterAudioFile && videoData.ambientScoreFile && (
        <Audio src={staticFile(videoData.ambientScoreFile)} volume={0.22} />
      )}

      <TransitionSeries>
        {scenes.map((scene, index) => {
          const durationFrames = paddedDurations[index];
        const cleanMedia = (scene.mediaFile || '').replace(/^\/?public\//, '');

        return (
          <React.Fragment key={`scene-${index}`}>
            <TransitionSeries.Sequence durationInFrames={durationFrames}>
              <AbsoluteFill>
                <CinemaBackdrop
                  mediaFile={cleanMedia}
                  mediaKind={scene.mediaKind}
                  cameraMotion={scene.cameraMotion}
                  sceneType={scene.type}
                  motionDurationInFrames={durationFrames}
                  beatSync={videoData.beatSync}
                  beatTimestamps={videoData.beatTimestamps}
                  accentColor={themeColor}
                  isCinemaMode={Boolean(videoData.isLandscape && videoData.mode === 'cinema')}
                />
                <ThreeDScenes
                  sceneType={scene.type}
                  themeColor={themeColor}
                  barValues={scene.barValues}
                />
                <SceneCardOverlay scene={scene} themeColor={themeColor} />
                {index > 0 && !videoData.masterAudioFile && (
                  <Sequence
                    from={0}
                    durationInFrames={Math.min(durationFrames, Math.ceil(fps * 1.6))}
                    layout="none"
                  >
                    {scene.sfxCue === 'boom' && videoData.sfxBoomFile ? (
                      <Audio src={staticFile(videoData.sfxBoomFile)} volume={0.52} />
                    ) : scene.sfxCue === 'pulse' && videoData.sfxPopFile ? (
                      <Audio src={staticFile(videoData.sfxPopFile)} volume={0.42} />
                    ) : videoData.sfxWhooshFile ? (
                      <Audio src={staticFile(videoData.sfxWhooshFile)} volume={0.42} />
                    ) : null}
                  </Sequence>
                )}
                <TransitionFlash />
              </AbsoluteFill>
            </TransitionSeries.Sequence>
            {index < scenes.length - 1 &&
              (index % 3 === 0 ? (
                <TransitionSeries.Transition
                  presentation={fade()}
                  timing={springTiming({
                    durationInFrames: transitionFrames,
                    config: { damping: 200 },
                  })}
                />
              ) : index % 3 === 1 ? (
                <TransitionSeries.Transition
                  presentation={slide({ direction: 'from-right' })}
                  timing={springTiming({
                    durationInFrames: transitionFrames,
                    config: { damping: 200 },
                  })}
                />
              ) : (
                <TransitionSeries.Transition
                  presentation={wipe({ direction: 'from-left' })}
                  timing={springTiming({
                    durationInFrames: transitionFrames,
                    config: { damping: 200 },
                  })}
                />
              ))}
          </React.Fragment>
        );
        })}
      </TransitionSeries>

      <div
        style={{
          position: 'absolute',
          top: videoData.isLandscape ? '5%' : '14%',
          left: 0,
          right: 0,
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
          textAlign: 'center',
        }}
      >
        {videoData.brandTag || 'IFXTRADES'}
      </div>

      <SubtitleOverlay words={videoData.words || []} themeColor={themeColor} />
    </AbsoluteFill>
  );
};
