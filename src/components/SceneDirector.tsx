import React from 'react';
import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig } from 'remotion';
import type { SceneItem } from '../types';

type Props = {
  scene: SceneItem;
  themeColor: string;
  sceneIndex: number;
  isLandscape?: boolean;
};

const Kicker: React.FC<{ children: React.ReactNode; color: string; muted?: boolean }> = ({
  children, color, muted = false,
}) => (
  <div style={{
    color: muted ? '#CBD5E1' : color,
    font: '700 12px "JetBrains Mono", monospace',
    letterSpacing: '0.16em',
    textTransform: 'uppercase',
    marginBottom: 16,
  }}>{children}</div>
);

const Headline: React.FC<{
  children: string;
  size: number;
  align?: 'left' | 'center' | 'right';
  uppercase?: boolean;
  color?: string;
  accentColor?: string;
  fontFamily?: string;
}> = ({ children, size, align = 'left', uppercase = false, color = '#F8FAFC', accentColor = '#D4AF37', fontFamily = '\"Montserrat\", \"Arial Black\", system-ui, sans-serif' }) => (
  <h1 style={{
    fontFamily: '"Montserrat", "Arial Black", system-ui, sans-serif',
    fontSize: size,
    fontWeight: 900,
    lineHeight: 0.98,
    letterSpacing: '-0.045em',
    color,
    textAlign: align,
    textTransform: uppercase ? 'uppercase' : 'none',
    textWrap: 'balance',
    overflowWrap: 'break-word',
    wordBreak: 'normal',
    maxWidth: '100%',
    textShadow: '0 5px 24px rgba(0,0,0,0.78)',
    margin: 0,
  }}>
    <span style={{ color: accentColor }}>{children.trim().split(/\s+/)[0]}</span>{' '}{children.trim().split(/\s+/).slice(1).join(' ')}
  </h1>
);

const Subline: React.FC<{ children?: string; size: number }> = ({ children, size }) => (
  children ? <p style={{
    color: 'rgba(248,250,252,0.84)',
    font: `500 ${size}px Inter, system-ui, sans-serif`,
    lineHeight: 1.35,
    maxWidth: '55em',
    margin: '16px 0 0',
    textShadow: '0 3px 16px rgba(0,0,0,0.75)',
  }}>{children}</p> : null
);

const BulletList: React.FC<{ items?: string[]; color: string; horizontal?: boolean }> = ({
  items, color, horizontal = false,
}) => {
  if (!items?.length) return null;
  return <div style={{
    display: horizontal ? 'flex' : 'grid',
    gridTemplateColumns: horizontal ? undefined : '1fr',
    flexDirection: horizontal ? 'row' : undefined,
    gap: horizontal ? 12 : 10,
    width: '100%',
    marginTop: 22,
    alignItems: 'stretch',
  }}>
    {items.slice(0, 4).map((item, index) => (
      <div key={`${index}-${item}`} style={{
        flex: horizontal ? 1 : undefined,
        display: 'flex',
        alignItems: 'flex-start',
        gap: 12,
        minWidth: 0,
        padding: horizontal ? '15px 13px' : '12px 16px',
        borderLeft: `2px solid ${color}`,
        background: 'rgba(3,7,13,0.70)',
        color: '#F1F5F9',
        fontSize: horizontal ? 18 : 21,
        fontWeight: 650,
        lineHeight: 1.25,
        backdropFilter: 'blur(8px)',
      }}>
        <span style={{
          color,
          font: '800 13px "JetBrains Mono", monospace',
          paddingTop: 3,
          flexShrink: 0,
        }}>{String(index + 1).padStart(2, '0')}</span>
        <span>{item}</span>
      </div>
    ))}
  </div>;
};

export const SceneDirector: React.FC<Props> = ({
  scene, themeColor, sceneIndex, isLandscape = false,
}) => {
  const frame = useCurrentFrame();
  const { height, width, fps } = useVideoConfig();
  const treatment = scene.visualTreatment || 'documentary_lower_third';
  const displayFontFamily =
    treatment === 'editorial_cover'
      ? '"Noto Serif", Georgia, serif'
      : treatment === 'photo_essay' || treatment === 'immersive_photo' || treatment === 'documentary_lower_third'
        ? 'Lato, "Noto Sans", sans-serif'
        : '"Montserrat", "Arial Black", system-ui, sans-serif';
  const enter = interpolate(frame, [0, Math.max(6, fps * 0.55)], [0, 1], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
  });
  const lift = interpolate(frame, [0, Math.max(6, fps * 0.65)], [28, 0], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
  });
  const titleSize = Math.max(36, Math.min(
    isLandscape ? 86 : 78,
    height * (isLandscape ? 0.075 : 0.052),
  ));
  const smallSize = Math.max(24, Math.min(34, height * 0.019));
  const maxWidth = Math.min(width * (isLandscape ? 0.67 : 0.88), 1120);
  const side = scene.textSide === 'right' ? 'right' : 'left';
  const textBase: React.CSSProperties = {
    opacity: enter,
    transform: `translateY(${lift}px)`,
    pointerEvents: 'none',
    boxSizing: 'border-box',
  };
  const kicker = scene.kicker || '';
  const title = scene.headline || '';
  const subline = scene.subline;
  const titleLength = title.trim().length;
  const fittedTitleSize = Math.max(
    isLandscape ? 34 : 30,
    Math.round(titleSize * Math.min(1, Math.pow(32 / Math.max(1, titleLength), 0.42))),
  );
  const titleNode = <Headline accentColor={themeColor} fontFamily={displayFontFamily} size={fittedTitleSize}>{title}</Headline>;
  const sublineNode = <Subline size={smallSize}>{subline}</Subline>;

  if (treatment === 'kinetic_typography') {
    const scale = interpolate(frame, [0, Math.max(8, fps * 0.7)], [0.88, 1], {
      extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
    });
    return <AbsoluteFill style={{ ...textBase, justifyContent: 'center', alignItems: 'center', padding: '12%' }}>
      <div style={{ width: '100%', maxWidth, transform: `scale(${scale})`, textAlign: 'center' }}>
        {kicker && <Kicker color={themeColor}>{kicker}</Kicker>}
        <Headline accentColor={themeColor} fontFamily={displayFontFamily} size={Math.max(42, Math.min(isLandscape ? 104 : 86, height * 0.072, fittedTitleSize * 1.22))} align="center" uppercase>{title}</Headline>
        <div style={{ width: '22%', height: 4, margin: '28px auto 0', background: themeColor }} />
        <div style={{ textAlign: 'center' }}><Subline size={smallSize}>{subline}</Subline></div>
      </div>
    </AbsoluteFill>;
  }

  if (treatment === 'vertical_timeline') {
    return <AbsoluteFill style={{
      ...textBase, justifyContent: 'center', alignItems: 'flex-start',
      padding: isLandscape ? '9% 8% 25%' : '12% 7% 29%',
    }}>
      <div style={{ width: '100%', maxWidth }}>
        {kicker && <Kicker color={themeColor}>{kicker}</Kicker>}
        {titleNode}
        {sublineNode}
        <BulletList items={scene.bullets} color={themeColor} />
      </div>
    </AbsoluteFill>;
  }

  if (treatment === 'process_blueprint') {
    return <AbsoluteFill style={{
      ...textBase, justifyContent: 'center', alignItems: 'center',
      padding: isLandscape ? '9% 9% 25%' : '12% 7% 29%',
    }}>
      <div style={{ width: '100%', maxWidth }}>
        <div style={{ borderBottom: `1px solid ${themeColor}99`, paddingBottom: 18, marginBottom: 12 }}>
          {kicker && <Kicker color={themeColor}>{kicker} / SYSTEM MAP</Kicker>}
          {titleNode}
          {sublineNode}
        </div>
        <BulletList items={scene.bullets} color={themeColor} horizontal={isLandscape} />
        {scene.bullets?.length ? (
          <div style={{
            display: 'flex', justifyContent: 'space-between', marginTop: 18,
            opacity: 0.78, color: themeColor, font: '700 11px "JetBrains Mono", monospace',
            letterSpacing: '0.13em',
          }}><span>INPUT</span><span>PROCESS</span><span>OUTCOME</span></div>
        ) : null}
      </div>
    </AbsoluteFill>;
  }

  if (treatment === 'comparative_split') {
    return <AbsoluteFill style={{
      ...textBase, justifyContent: 'flex-end', padding: isLandscape ? '10% 7% 25%' : '12% 6% 29%',
    }}>
      <div style={{ maxWidth, width: '100%', margin: '0 auto' }}>
        {kicker && <Kicker color={themeColor}>{kicker}</Kicker>}
        <Headline accentColor={themeColor} fontFamily={displayFontFamily} size={Math.max(34, Math.min(68, height * 0.045))}>{title}</Headline>
        <div style={{
          display: 'flex', flexDirection: isLandscape ? 'row' : 'column',
          gap: 12, marginTop: 24,
        }}>
          <div style={{
            flex: 1, padding: 20, minHeight: isLandscape ? 150 : 92,
            border: '1px solid rgba(248,113,113,0.66)',
            background: 'linear-gradient(135deg,rgba(127,29,29,0.78),rgba(10,14,22,0.92))',
          }}>
            <Kicker color="#FCA5A5">{scene.leftLabel || 'SIDE A'}</Kicker>
            <div style={{ color: '#F8FAFC', fontSize: smallSize, fontWeight: 800 }}>{subline || 'First perspective'}</div>
          </div>
          <div style={{
            flex: 1, padding: 20, minHeight: isLandscape ? 150 : 92,
            border: `1px solid ${themeColor}`,
            background: `linear-gradient(135deg,${themeColor}33,rgba(10,14,22,0.94))`,
          }}>
            <Kicker color={themeColor}>{scene.rightLabel || 'SIDE B'}</Kicker>
            <div style={{ color: '#FFFFFF', fontSize: smallSize, fontWeight: 800 }}>{scene.bullets?.[0] || 'Second perspective'}</div>
          </div>
        </div>
      </div>
    </AbsoluteFill>;
  }

  if (treatment === 'data_stage' || treatment === 'market_chart') {
    const bars = scene.barValues?.filter((bar) => Number.isFinite(bar.value) && bar.value >= 0) || [];
    const maxValue = Math.max(1, ...bars.map((bar) => bar.value));
    return <AbsoluteFill style={{
      ...textBase, justifyContent: 'flex-start', alignItems: 'flex-start',
      padding: isLandscape ? '10% 8% 25%' : '12% 7% 29%',
    }}>
      <div style={{ width: '100%', maxWidth }}>
        {kicker && <Kicker color={themeColor}>{kicker} / {bars.length ? 'SOURCE DATA' : 'VISUAL ANALYSIS'}</Kicker>}
        <Headline size={Math.max(34, Math.min(66, height * 0.044))}>{title}</Headline>
        {sublineNode}
        {scene.statValue && <div style={{
          font: `900 ${Math.max(48, Math.min(86, height * 0.064))}px Montserrat, sans-serif`,
          color: themeColor, marginTop: 24, textShadow: `0 0 32px ${themeColor}55`,
        }}>{scene.statValue}</div>}
        {bars.length > 0 && <div style={{ display: 'flex', gap: 14, alignItems: 'end', height: isLandscape ? 190 : 230, marginTop: 26 }}>
          {bars.slice(0, 6).map((bar, index) => (
            <div key={bar.label + index} style={{ flex: 1, minWidth: 0, height: '100%', display: 'flex', flexDirection: 'column', justifyContent: 'end' }}>
              <div style={{ color: '#F8FAFC', fontSize: 15, marginBottom: 7 }}>{bar.value}</div>
              <div style={{
                height: `${Math.max(4, (bar.value / maxValue) * 78)}%`,
                background: index === bars.length - 1 ? themeColor : 'linear-gradient(180deg,rgba(148,163,184,0.9),rgba(51,65,85,0.75))',
                borderTop: `3px solid ${index === bars.length - 1 ? '#FFFFFF' : themeColor}`,
              }} />
              <div style={{ color: '#CBD5E1', fontSize: 13, lineHeight: 1.1, marginTop: 8 }}>{bar.label}</div>
            </div>
          ))}
        </div>}
        {!bars.length && <div style={{
          borderLeft: `3px solid ${themeColor}`, paddingLeft: 18,
          color: '#CBD5E1', font: '600 15px "JetBrains Mono", monospace',
          marginTop: 26, letterSpacing: '0.08em',
        }}>CONCEPTUAL VISUAL — NO UNSOURCED VALUES</div>}
      </div>
    </AbsoluteFill>;
  }

  if (treatment === 'cinema_end_frame') {
    return <AbsoluteFill style={{
      ...textBase, justifyContent: 'center', alignItems: 'center',
      padding: isLandscape ? '10% 12% 24%' : '12% 9% 28%', textAlign: 'center',
    }}>
      <div style={{ maxWidth: maxWidth * 0.9 }}>
        <div style={{ width: 70, height: 2, background: themeColor, margin: '0 auto 28px' }} />
        {kicker && <Kicker color={themeColor}>{kicker}</Kicker>}
        <Headline accentColor={themeColor} fontFamily={displayFontFamily} size={Math.max(42, Math.min(90, height * 0.065))} align="center">{title}</Headline>
        <div style={{ width: 130, height: 1, background: 'rgba(255,255,255,0.42)', margin: '26px auto' }} />
        <div style={{ textAlign: 'center' }}><Subline size={smallSize}>{subline}</Subline></div>
      </div>
    </AbsoluteFill>;
  }

  if (treatment === 'editorial_split' || treatment === 'cinematic_side_caption') {
    const panelWidth = treatment === 'cinematic_side_caption' ? '43%' : '52%';
    const panelSide: React.CSSProperties = side === 'right'
      ? { right: 0, borderLeft: `2px solid ${themeColor}99` }
      : { left: 0, borderRight: `2px solid ${themeColor}99` };
    return <AbsoluteFill style={{
      ...textBase, alignItems: side === 'right' ? 'flex-end' : 'flex-start',
      justifyContent: 'center',
    }}>
      <div style={{
        ...panelSide, position: 'absolute', top: '10%', bottom: '21%',
        width: panelWidth, padding: isLandscape ? '5% 4%' : '8% 5%',
        display: 'flex', flexDirection: 'column', justifyContent: 'center',
        boxSizing: 'border-box',
        background: 'linear-gradient(145deg,rgba(3,7,13,0.9),rgba(3,7,13,0.56))',
      }}>
        {kicker && <Kicker color={themeColor}>{kicker}</Kicker>}
        <Headline size={Math.max(34, Math.min(68, height * 0.047))}>{title}</Headline>
        <Subline size={smallSize}>{subline}</Subline>
        <BulletList items={scene.bullets} color={themeColor} />
      </div>
    </AbsoluteFill>;
  }

  if (treatment === 'editorial_cover') {
    return <AbsoluteFill style={{
      ...textBase, justifyContent: 'flex-end', alignItems: 'flex-start',
      padding: isLandscape ? '9% 8% 23%' : '12% 7% 25%',
    }}>
      <div style={{ maxWidth: maxWidth * 0.92, borderLeft: `5px solid ${themeColor}`, paddingLeft: 22 }}>
        {kicker && <Kicker color={themeColor}>{kicker}</Kicker>}
        <Headline accentColor={themeColor} fontFamily={displayFontFamily} size={Math.max(34, Math.min(76, height * 0.058, fittedTitleSize * 1.12))} uppercase>{title}</Headline>
        <Subline size={smallSize}>{subline}</Subline>
      </div>
    </AbsoluteFill>;
  }

  if (treatment === 'hero_full_bleed') {
    return <AbsoluteFill style={{
      ...textBase, justifyContent: 'flex-end', alignItems: 'flex-start',
      padding: isLandscape ? '8% 8% 23%' : '12% 7% 25%',
    }}>
      <div style={{ maxWidth: maxWidth * 0.88 }}>
        {kicker && <Kicker color={themeColor}>{kicker}</Kicker>}
        <Headline accentColor={themeColor} fontFamily={displayFontFamily} size={titleSize} uppercase>{title}</Headline>
        <Subline size={smallSize}>{subline}</Subline>
      </div>
    </AbsoluteFill>;
  }

  if (treatment === 'orbit_stage') {
    return <AbsoluteFill style={{
      ...textBase, justifyContent: 'flex-start', alignItems: 'flex-start',
      padding: isLandscape ? '8% 7%' : '14% 7%',
    }}>
      <div style={{ width: '100%', maxWidth: maxWidth * 0.7 }}>
        {kicker && <Kicker color={themeColor}>{kicker}</Kicker>}
        <Headline accentColor={themeColor} fontFamily={displayFontFamily} size={Math.max(34, Math.min(62, height * 0.043))}>{title}</Headline>
        <Subline size={smallSize}>{subline}</Subline>
      </div>
    </AbsoluteFill>;
  }

  if (treatment === 'photo_essay' || treatment === 'immersive_photo') {
    return <AbsoluteFill style={{
      ...textBase, justifyContent: 'flex-end', alignItems: 'flex-start',
      padding: isLandscape ? '8% 8% 22%' : '10% 7% 27%',
    }}>
      <div style={{
        maxWidth: maxWidth * 0.72, borderLeft: `2px solid ${themeColor}`,
        padding: '4px 0 4px 18px',
      }}>
        {kicker && <Kicker color={themeColor} muted>{kicker}</Kicker>}
        <Headline accentColor={themeColor} fontFamily={displayFontFamily} size={Math.max(30, Math.min(58, height * 0.04))}>{title}</Headline>
        <Subline size={smallSize}>{subline}</Subline>
      </div>
    </AbsoluteFill>;
  }

  // Default composition is a restrained documentary lower-third, not a centred card.
  return <AbsoluteFill style={{
    ...textBase, justifyContent: 'flex-end', alignItems: 'flex-start',
    padding: isLandscape ? '8% 8% 24%' : '10% 7% 29%',
  }}>
    <div style={{
      maxWidth: maxWidth * 0.82, borderLeft: `4px solid ${themeColor}`,
      paddingLeft: 20,
      background: 'linear-gradient(90deg,rgba(4,8,14,0.68),transparent)',
    }}>
      {kicker && <Kicker color={themeColor}>{kicker}</Kicker>}
      <Headline accentColor={themeColor} fontFamily={displayFontFamily} size={Math.max(34, Math.min(66, height * 0.047))}>{title}</Headline>
      <Subline size={smallSize}>{subline}</Subline>
    </div>
  </AbsoluteFill>;
};
