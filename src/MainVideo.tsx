import React from 'react';
import {
  AbsoluteFill,
  Audio,
  spring,
  interpolate,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from 'remotion';
import { TransitionSeries, linearTiming } from '@remotion/transitions';
import { slide } from '@remotion/transitions/slide';
import { fade } from '@remotion/transitions/fade';
import { wipe } from '@remotion/transitions/wipe';
import { whoosh, whip, ding } from '@remotion/sfx';
import { SceneItem, VideoProps } from './types';
import { CinemaBackdrop } from './components/CinemaBackdrop';
import { ThreeDOrbitalScene, ThreeDBarChartScene } from './components/ThreeDScenes';

const ICE = '#38BDF8';

const AnimatedCandles: React.FC<{ progress: number }> = ({ progress }) => {
  const candles = [
    { x: 110, open: 220, close: 170, high: 150, low: 240, bull: true },
    { x: 210, open: 170, close: 130, high: 110, low: 190, bull: true },
    { x: 310, open: 130, close: 185, high: 115, low: 205, bull: false },
    { x: 410, open: 185, close: 248, high: 175, low: 278, bull: false },
    { x: 510, open: 248, close: 140, high: 120, low: 265, bull: true },
    { x: 610, open: 140, close: 75, high: 55, low: 155, bull: true },
    { x: 710, open: 75, close: 35, high: 20, low: 90, bull: true },
  ];

  return (
    <svg width="100%" height="280" viewBox="0 0 840 310" style={{ marginTop: 22 }}>
      <line x1="60" y1="255" x2="780" y2="255" stroke="#EF4444" strokeWidth="2.5" strokeDasharray="10 8" opacity={0.9} />
      <text x="68" y="286" fill="#EF4444" fontSize="21" fontWeight="800" fontFamily="sans-serif">
        LIQUIDITY SWEEP ZONE
      </text>
      {candles.map((c, idx) => {
        const appear = interpolate(progress, [idx * 0.1, idx * 0.1 + 0.25], [0, 1], {
          extrapolateLeft: 'clamp',
          extrapolateRight: 'clamp',
        });
        const top = Math.min(c.open, c.close);
        const height = Math.max(12, Math.abs(c.close - c.open));
        const color = c.bull ? '#10B981' : '#EF4444';
        return (
          <g key={idx} opacity={appear} transform={`translate(0, ${(1 - appear) * 24})`}>
            <line x1={c.x} y1={c.high} x2={c.x} y2={c.low} stroke={color} strokeWidth="5" />
            <rect x={c.x - 22} y={top} width="44" height={height} rx="6" fill={color} />
          </g>
        );
      })}
    </svg>
  );
};

const SceneOverlay: React.FC<{
  scene: SceneItem;
  themeColor: string;
  isLandscape: boolean;
  isCinemaMode: boolean;
}> = ({ scene, themeColor, isLandscape, isCinemaMode }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const enter = spring({ frame, fps, config: { damping: 15, stiffness: 110 } });
  const slideUp = interpolate(enter, [0, 1], [44, 0]);
  const chartProgress = interpolate(frame, [0, 42], [0, 1], { extrapolateRight: 'clamp' });
  const accent = scene.accentColor || themeColor;
  const hasRichBackdrop = scene.mediaKind === 'video' || scene.mediaKind === 'image';

  if (scene.type === 'cinema_hero' || scene.type === 'cinema_outro') {
    return (
      <AbsoluteFill>
        <CinemaBackdrop
          mediaFile={scene.mediaFile}
          mediaKind={scene.mediaKind}
          cameraMotion={scene.cameraMotion || 'dolly_push'}
          accentColor={accent}
          isCinemaMode={isCinemaMode}
        />
        <AbsoluteFill
          style={{
            justifyContent: 'center',
            alignItems: 'center',
            textAlign: 'center',
            padding: isLandscape ? '110px 180px 190px 180px' : '160px 64px 360px 64px',
            opacity: enter,
            transform: `translateY(${slideUp}px)`,
          }}
        >
          <div
            style={{
              display: 'inline-block',
              padding: '10px 26px',
              borderRadius: 999,
              backgroundColor: 'rgba(6, 8, 13, 0.72)',
              border: `1.5px solid ${accent}`,
              color: accent,
              fontSize: 23,
              fontWeight: 900,
              letterSpacing: 4,
              textTransform: 'uppercase',
              marginBottom: 26,
              backdropFilter: 'blur(12px)',
            }}
          >
            {scene.kicker}
          </div>

          <div
            style={{
              color: '#FFFFFF',
              fontSize: isLandscape ? 76 : 74,
              fontWeight: 900,
              lineHeight: 1.08,
              letterSpacing: -1.5,
              textShadow: '0 14px 48px rgba(0,0,0,0.92)',
            }}
          >
            {scene.headline}
          </div>

          {scene.subline && (
            <div
              style={{
                marginTop: 24,
                color: '#E2E8F0',
                fontSize: isLandscape ? 32 : 34,
                fontWeight: 600,
                maxWidth: 880,
                lineHeight: 1.35,
                textShadow: '0 6px 24px rgba(0,0,0,0.9)',
              }}
            >
              {scene.subline}
            </div>
          )}

          {scene.statValue && (
            <div
              style={{
                marginTop: 32,
                fontSize: isLandscape ? 110 : 124,
                fontWeight: 900,
                color: accent,
                textShadow: `0 0 55px ${accent}88`,
              }}
            >
              {scene.statValue}
            </div>
          )}
        </AbsoluteFill>
      </AbsoluteFill>
    );
  }

  return (
    <AbsoluteFill>
      <CinemaBackdrop
        mediaFile={scene.mediaFile}
        mediaKind={scene.mediaKind}
        cameraMotion={scene.cameraMotion || 'zoom_in'}
        accentColor={accent}
        isCinemaMode={isCinemaMode}
      />
      <AbsoluteFill
        style={{
          justifyContent: 'center',
          alignItems: 'center',
          padding: isLandscape ? '100px 150px 185px 150px' : '135px 52px 350px 52px',
          opacity: enter,
          transform: `translateY(${slideUp}px)`,
        }}
      >
        <div
          style={{
            width: '100%',
            background: hasRichBackdrop ? 'rgba(9, 13, 22, 0.78)' : 'rgba(13, 18, 30, 0.88)',
            backdropFilter: 'blur(18px)',
            border: `1.5px solid ${accent}66`,
            borderRadius: 34,
            padding: isLandscape ? '40px 52px' : '46px 42px',
            boxShadow: '0 32px 96px rgba(0,0,0,0.85)',
          }}
        >
          <div
            style={{
              color: accent,
              fontSize: 23,
              fontWeight: 900,
              letterSpacing: 3.5,
              textTransform: 'uppercase',
              marginBottom: 12,
            }}
          >
            {scene.kicker}
          </div>

          <div
            style={{
              color: '#F8FAFC',
              fontSize: isLandscape ? 50 : 54,
              fontWeight: 900,
              lineHeight: 1.12,
              letterSpacing: -1,
            }}
          >
            {scene.headline}
          </div>

          {scene.statValue && (
            <div
              style={{
                marginTop: 24,
                fontSize: isLandscape ? 92 : 108,
                fontWeight: 900,
                color: ICE,
                textShadow: '0 0 42px rgba(56, 189, 248, 0.5)',
              }}
            >
              {scene.statValue}
            </div>
          )}

          {scene.type === 'three_d_globe' && <ThreeDOrbitalScene color={accent} />}
          {scene.type === 'three_d_bars' && <ThreeDBarChartScene bars={scene.barValues} color={accent} />}
          {scene.type === 'candlestick_chart' && <AnimatedCandles progress={chartProgress} />}

          {scene.type === 'split_compare' && (
            <div style={{ display: 'flex', gap: 22, marginTop: 30 }}>
              <div
                style={{
                  flex: 1,
                  background: 'rgba(239,68,68,0.16)',
                  border: '1px solid #EF4444',
                  borderRadius: 22,
                  padding: 26,
                }}
              >
                <div style={{ color: '#FCA5A5', fontSize: 21, fontWeight: 800 }}>CONVENTIONAL</div>
                <div style={{ color: '#FFF', fontSize: 30, fontWeight: 800, marginTop: 10 }}>
                  {scene.leftLabel || 'Slow & Reactive'}
                </div>
              </div>
              <div
                style={{
                  flex: 1,
                  background: 'rgba(16,185,129,0.16)',
                  border: '1px solid #10B981',
                  borderRadius: 22,
                  padding: 26,
                }}
              >
                <div style={{ color: '#6EE7B7', fontSize: 21, fontWeight: 800 }}>NEXT-GEN EDGE</div>
                <div style={{ color: '#FFF', fontSize: 30, fontWeight: 800, marginTop: 10 }}>
                  {scene.rightLabel || 'Autonomous Precision'}
                </div>
              </div>
            </div>
          )}

          {scene.bullets && scene.bullets.length > 0 && (
            <div style={{ marginTop: 26, display: 'flex', flexDirection: 'column', gap: 16 }}>
              {scene.bullets.map((b, i) => {
                const itemSpring = spring({ frame: Math.max(0, frame - i * 7), fps, config: { damping: 15 } });
                return (
                  <div
                    key={i}
                    style={{
                      opacity: itemSpring,
                      transform: `translateX(${interpolate(itemSpring, [0, 1], [-26, 0])}px)`,
                      display: 'flex',
                      alignItems: 'center',
                      gap: 18,
                      background: 'rgba(255,255,255,0.06)',
                      padding: '17px 24px',
                      borderRadius: 18,
                      borderLeft: `5px solid ${accent}`,
                    }}
                  >
                    <span style={{ color: accent, fontSize: 27, fontWeight: 900 }}>0{i + 1}</span>
                    <span style={{ color: '#F1F5F9', fontSize: 29, fontWeight: 600 }}>{b}</span>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

export const MainVideo: React.FC<VideoProps & { isLandscape?: boolean }> = ({
  brandTag,
  themeColor = '#D4AF37',
  mode = 'shorts',
  scenes,
  words,
  isLandscape = false,
}) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const currentSec = frame / fps;
  const isCinemaMode = mode === 'cinema' || isLandscape;

  const activeIdx = words.findIndex((w) => currentSec >= w.start && currentSec <= w.end + 0.16);
  const windowSize = isLandscape ? 7 : 4;
  const windowStart = activeIdx >= 0 ? Math.floor(activeIdx / windowSize) * windowSize : 0;
  const visibleWords = words.slice(windowStart, windowStart + windowSize);

  const progressPct = (frame / durationInFrames) * 100;
  const transitionFrames = 14;

  return (
    <AbsoluteFill style={{ backgroundColor: '#05070B', fontFamily: 'Inter, system-ui, sans-serif' }}>
      <Audio src={staticFile('voiceover.mp3')} volume={1.0} />
      <Audio src={staticFile('ambient_score.mp3')} volume={0.18} loop />

      <div style={{ position: 'absolute', top: isCinemaMode ? 84 : 0, left: 0, right: 0, zIndex: 45 }}>
        <div
          style={{
            height: 6,
            width: `${progressPct}%`,
            background: `linear-gradient(90deg, ${themeColor}, ${ICE})`,
          }}
        />
        <div style={{ display: 'flex', justifyContent: 'space-between', padding: '26px 54px', alignItems: 'center' }}>
          <span
            style={{
              color: themeColor,
              fontWeight: 900,
              fontSize: 25,
              letterSpacing: 3,
              textShadow: '0 2px 12px rgba(0,0,0,0.9)',
            }}
          >
            {brandTag || 'IFXTRADES'}
          </span>
          <span
            style={{
              color: '#94A3B8',
              fontWeight: 800,
              fontSize: 19,
              letterSpacing: 2,
              backgroundColor: 'rgba(5,7,11,0.65)',
              padding: '6px 14px',
              borderRadius: 8,
            }}
          >
            {isCinemaMode ? 'CINEMA ENGINE 4K-MASTER' : 'AI STUDIO'}
          </span>
        </div>
      </div>

      <TransitionSeries>
        {scenes.map((scene, index) => {
          const baseDuration = Math.max(24, Math.ceil((scene.endSec - scene.startSec) * fps));
          const compensatedDuration = index < scenes.length - 1 ? baseDuration + transitionFrames : baseDuration;
          const sfxTrack =
            scene.sfxCue === 'boom' ? whip : scene.sfxCue === 'pulse' ? ding : whoosh;

          return (
            <React.Fragment key={index}>
              <TransitionSeries.Sequence durationInFrames={compensatedDuration}>
                {index > 0 && <Audio src={sfxTrack} volume={0.28} />}
                <SceneOverlay
                  scene={scene}
                  themeColor={themeColor}
                  isLandscape={isLandscape}
                  isCinemaMode={isCinemaMode}
                />
              </TransitionSeries.Sequence>
              {index < scenes.length - 1 && (
                <TransitionSeries.Transition
                  presentation={
                    index % 3 === 0
                      ? fade()
                      : index % 3 === 1
                      ? wipe({ direction: 'from-left' })
                      : slide({ direction: 'from-right' })
                  }
                  timing={linearTiming({ durationInFrames: transitionFrames })}
                />
              )}
            </React.Fragment>
          );
        })}
      </TransitionSeries>

      {visibleWords.length > 0 && (
        <div
          style={{
            position: 'absolute',
            bottom: isCinemaMode ? 105 : 140,
            left: 48,
            right: 48,
            display: 'flex',
            flexWrap: 'wrap',
            justifyContent: 'center',
            gap: isCinemaMode ? 10 : 14,
            zIndex: 50,
          }}
        >
          {visibleWords.map((w, idx) => {
            const isSpeaking = currentSec >= w.start && currentSec <= w.end + 0.16;
            if (isCinemaMode) {
              return (
                <span
                  key={idx}
                  style={{
                    fontSize: 42,
                    fontWeight: 800,
                    padding: '4px 10px',
                    borderRadius: 8,
                    backgroundColor: 'rgba(0, 0, 0, 0.72)',
                    color: isSpeaking ? themeColor : '#F8FAFC',
                    textShadow: '0 2px 10px rgba(0,0,0,0.95)',
                    transform: isSpeaking ? 'scale(1.06)' : 'scale(1)',
                  }}
                >
                  {w.word}
                </span>
              );
            }
            return (
              <span
                key={idx}
                style={{
                  fontSize: 52,
                  fontWeight: 900,
                  textTransform: 'uppercase',
                  padding: '8px 18px',
                  borderRadius: 14,
                  backgroundColor: isSpeaking ? themeColor : 'rgba(5, 7, 11, 0.86)',
                  color: isSpeaking ? '#05070B' : '#FFFFFF',
                  transform: isSpeaking ? 'scale(1.08)' : 'scale(1)',
                  boxShadow: isSpeaking ? `0 10px 30px ${themeColor}88` : 'none',
                }}
              >
                {w.word}
              </span>
            );
          })}
        </div>
      )}
    </AbsoluteFill>
  );
};
