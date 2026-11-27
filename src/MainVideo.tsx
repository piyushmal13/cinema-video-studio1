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
import { SceneDirector } from './components/SceneDirector';
import { VideoProps, SceneItem } from './types';

const defaultVideoData = rawVideoData as VideoProps;

const SubtitleOverlay: React.FC<{
  words: VideoProps['words'];
  scenes: SceneItem[];
  themeColor: string;
  isLandscape?: boolean;
}> = ({ words, scenes, themeColor, isLandscape = false }) => {
  const frame = useCurrentFrame();
  const { fps, height } = useVideoConfig();
  const currentSec = frame / fps;
  if (!words || words.length === 0) return null;

  const activeIndex = words.findIndex(
    (word) => currentSec >= word.start - 0.08 && currentSec <= word.end + 0.15
  );
  if (activeIndex < 0) return null;

  const scene = scenes.find(
    (item) => currentSec >= item.startSec && currentSec <= item.endSec
  );
  const style = scene?.captionStyle || 'documentary';
  const visibleWords = words.slice(activeIndex, Math.min(words.length, activeIndex + 4));
  const fontSize = Math.max(19, Math.min(34, height * (isLandscape ? 0.021 : 0.019)));
  const minimal = style === 'minimal';
  const documentary = style === 'documentary';
  const ticker = style === 'ticker';

  return (
    <div style={{
      position: 'absolute',
      bottom: isLandscape ? '10%' : '13%',
      left: ticker ? '5%' : '7%',
      right: ticker ? '5%' : '7%',
      display: 'flex',
      justifyContent: ticker || documentary ? 'flex-start' : 'center',
      flexWrap: 'wrap',
      alignItems: 'center',
      gap: minimal ? '5px' : '8px',
      zIndex: 30,
      pointerEvents: 'none',
      padding: ticker ? '11px 16px' : documentary ? '0 0 0 14px' : '8px 12px',
      borderLeft: ticker || documentary ? `3px solid ${themeColor}` : 'none',
      background: ticker
        ? 'rgba(3,7,13,0.88)'
        : documentary
          ? 'linear-gradient(90deg,rgba(3,7,13,0.72),transparent)'
          : 'transparent',
      maxWidth: isLandscape ? '76%' : undefined,
      margin: isLandscape && !ticker && !documentary ? '0 auto' : undefined,
    }}>
      {visibleWords.map((item, index) => {
        const current = index === 0;
        return (
          <span key={`${item.word}-${activeIndex + index}`} style={{
            fontFamily: ticker ? '"JetBrains Mono", monospace' : '"Montserrat", system-ui, sans-serif',
            fontSize: current ? fontSize : fontSize * 0.86,
            fontWeight: current ? 900 : 700,
            letterSpacing: ticker ? '0.01em' : '0.015em',
            textTransform: ticker ? 'none' : 'uppercase',
            color: current ? (documentary ? '#FFFFFF' : themeColor) : '#F8FAFC',
            background: minimal ? 'transparent' : current ? 'rgba(4,8,14,0.78)' : 'rgba(4,8,14,0.56)',
            padding: minimal ? '0 2px' : '4px 9px',
            borderBottom: documentary && current ? `2px solid ${themeColor}` : 'none',
            borderRadius: minimal ? 0 : 5,
            textShadow: '0 3px 18px rgba(0,0,0,0.92)',
          }}>{item.word}</span>
        );
      })}
    </div>
  );
};

const SceneCardOverlay: React.FC<{
  scene: SceneItem;
  themeColor: string;
  sceneIndex: number;
}> = ({ scene, themeColor, sceneIndex }) => {
  const frame = useCurrentFrame();
  const { fps, height } = useVideoConfig();
  const opacity =
    scene.type === 'cinema_hero' ? 1 : Math.min(1, 0.25 + frame / 12);
  const translateY =
    scene.type === 'cinema_hero' ? 0 : Math.max(0, 18 - frame * 1.5);
  const layout =
    scene.type === 'cinema_hero' || scene.type === 'kinetic_type'
      ? 'hero'
      : scene.type === 'step_list' || scene.type === 'process_diagram'
        ? 'steps'
        : scene.type === 'cinema_outro'
          ? 'outro'
          : scene.type === 'three_d_globe' || scene.type === 'editorial_montage' || scene.type === 'data_viz' || sceneIndex % 2 === 1
            ? 'editorial'
            : 'glass';
  const headlineSize =
    layout === 'hero'
      ? Math.max(56, Math.min(104, height * 0.054))
      : layout === 'editorial'
        ? Math.max(42, Math.min(60, height * 0.032))
        : Math.max(44, Math.min(68, height * 0.035));
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
        width: 'auto',
        height: 'auto',
        top: '16%',
        bottom: '25%',
        left: '7%',
        right: '7%',
        opacity,
        transform: `translateY(${translateY}px)`,
        zIndex: 20,
        pointerEvents: 'none',
      }}
    >
      <div
        style={{
          width: '100%',
          maxWidth: layout === 'hero' ? 1040 : 960,
          display: 'flex',
          flexDirection: 'column',
          alignItems: layout === 'hero' || layout === 'editorial' ? 'flex-start' : 'center',
          textAlign: layout === 'hero' || layout === 'editorial' ? 'left' : 'center',
          gap: layout === 'hero' ? 24 : 18,
          padding: layout === 'hero' ? '36px 0 36px 30px' : '30px 28px',
          borderRadius: layout === 'hero' || layout === 'editorial' ? 8 : 28,
          border:
            layout === 'hero'
              ? 'none'
              : layout === 'editorial'
                ? `1px solid ${themeColor}88`
                : '1px solid transparent',
          borderLeft:
            layout === 'hero' || layout === 'editorial'
              ? `6px solid ${themeColor}`
              : undefined,
          background:
            layout === 'hero'
              ? 'linear-gradient(90deg, rgba(5,8,15,0.88), rgba(5,8,15,0.12))'
              : layout === 'editorial'
                ? 'linear-gradient(100deg, rgba(5,8,15,0.82), rgba(5,8,15,0.3))'
                : layout === 'outro'
                  ? `radial-gradient(ellipse at center, ${themeColor}2b, rgba(5,8,15,0.86) 72%)`
                  : `linear-gradient(145deg, rgba(5,8,15,0.76), rgba(8,13,24,0.54)) padding-box, conic-gradient(from ${frame * 7}deg, ${themeColor}cc, transparent 24%, rgba(255,255,255,0.12) 48%, transparent 68%, ${themeColor}cc) border-box`,
          backgroundClip: 'padding-box, border-box',
          boxShadow:
            layout === 'hero' || layout === 'editorial'
              ? `-18px 0 42px ${themeColor}22`
              : '0 24px 80px rgba(0,0,0,0.35)',
          backdropFilter: layout === 'hero' ? 'none' : 'blur(10px)',
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

        {(scene.type === 'step_list' || scene.type === 'process_diagram') && scene.bullets && scene.bullets.length > 0 && (
          <div
            style={{
              display: 'grid',
              gap: 12,
              width: '100%',
              marginTop: 6,
              textAlign: 'left',
            }}
          >
            {scene.bullets.slice(0, 4).map((bullet, index) => (
              <div
                key={`${index}-${bullet}`}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 14,
                  padding: '12px 16px',
                  borderLeft: `3px solid ${themeColor}`,
                  background: 'rgba(2,6,12,0.72)',
                  color: '#F8FAFC',
                  fontSize: Math.max(20, Math.min(28, height * 0.015)),
                  fontWeight: 700,
                }}
              >
                <span
                  style={{
                    color: themeColor,
                    font: '700 15px "JetBrains Mono", monospace',
                  }}
                >
                  {String(index + 1).padStart(2, '0')}
                </span>
                {bullet}
              </div>
            ))}
          </div>
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
          const cue =
            scene.sfxCue === 'boom'
              ? 'boom'
              : scene.sfxCue === 'pulse'
                ? 'pulse'
                : 'whoosh';
          const legacySfx =
            cue === 'boom'
              ? videoData.sfxBoomFile
              : cue === 'pulse'
                ? videoData.sfxPopFile
                : videoData.sfxWhooshFile;
          const sfxVariants = videoData.sfxFiles?.[cue] ?? (legacySfx ? [legacySfx] : []);
          const sfxFile = sfxVariants.length
            ? sfxVariants[(index + scene.headline.length) % sfxVariants.length]
            : undefined;

          return (
            <React.Fragment key={`scene-${index}`}>
              <TransitionSeries.Sequence durationInFrames={durationFrames}>
                <AbsoluteFill>
                  <CinemaBackdrop
                    mediaFile={cleanMedia}
                    mediaKind={scene.mediaKind}
                    cameraMotion={scene.cameraMotion}
                    sceneType={scene.type}
                    visualTreatment={scene.visualTreatment}
                    mediaFiles={scene.mediaFiles}
                    sceneIndex={index}
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
                    sceneIndex={index}
                  />
                  <SceneDirector
                    scene={scene}
                    themeColor={themeColor}
                    sceneIndex={index}
                    isLandscape={Boolean(videoData.isLandscape || videoData.format === 'landscape')}
                  />
                  {index > 0 && !videoData.masterAudioFile && sfxFile && (
                    <Sequence
                      from={0}
                      durationInFrames={Math.min(durationFrames, Math.ceil(fps * 1.6))}
                      layout="none"
                    >
                      <Audio
                        src={staticFile(sfxFile)}
                        volume={cue === 'boom' ? 0.52 : cue === 'pulse' ? 0.42 : 0.42}
                      />
                    </Sequence>
                  )}
                  <TransitionFlash />
                </AbsoluteFill>
              </TransitionSeries.Sequence>
              {index < scenes.length - 1 && (
                scene.transitionStyle === 'push' ? (
                  <TransitionSeries.Transition
                    presentation={slide({ direction: scene.textSide === 'right' ? 'from-left' : 'from-right' })}
                    timing={springTiming({ durationInFrames: transitionFrames, config: { damping: 200 } })}
                  />
                ) : scene.transitionStyle === 'wipe' ? (
                  <TransitionSeries.Transition
                    presentation={wipe({ direction: 'from-left' })}
                    timing={springTiming({ durationInFrames: transitionFrames, config: { damping: 200 } })}
                  />
                ) : scene.transitionStyle === 'flash' ? (
                  <TransitionSeries.Transition
                    presentation={wipe({ direction: 'from-bottom' })}
                    timing={springTiming({ durationInFrames: transitionFrames, config: { damping: 120 } })}
                  />
                ) : (
                  <TransitionSeries.Transition
                    presentation={fade()}
                    timing={springTiming({ durationInFrames: transitionFrames, config: { damping: 200 } })}
                  />
                )
              )}
            </React.Fragment>
          );
        })}
      </TransitionSeries>

      {videoData.brandTag && (
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
          {videoData.brandTag}
        </div>
      )}

      <SubtitleOverlay
        words={videoData.words || []}
        scenes={scenes}
        themeColor={themeColor}
        isLandscape={Boolean(videoData.isLandscape || videoData.format === 'landscape')}
      />
    </AbsoluteFill>
  );
};
