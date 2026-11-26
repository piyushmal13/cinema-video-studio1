import React from 'react';
import { ThreeCanvas } from '@remotion/three';
import { spring, useCurrentFrame, useVideoConfig } from 'remotion';
import type { SceneType } from '../types';

const NetworkCore: React.FC<{ color: string; phase: number }> = ({ color, phase }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const scale = spring({ frame, fps, config: { damping: 14, stiffness: 85 } });
  const rotY = (frame / fps) * 0.32 + phase;
  const rotX = Math.sin(frame / 40 + phase) * 0.12;

  return (
    <group scale={scale} rotation={[rotX, rotY, 0.14]}>
      <mesh>
        <sphereGeometry args={[1.34, 36, 24]} />
        <meshStandardMaterial
          color="#081522"
          metalness={0.52}
          roughness={0.46}
          emissive={color}
          emissiveIntensity={0.12}
        />
      </mesh>
      <mesh>
        <sphereGeometry args={[1.37, 24, 16]} />
        <meshBasicMaterial color={color} wireframe transparent opacity={0.32} />
      </mesh>
      <mesh rotation={[Math.PI / 2.4, 0, 0]}>
        <torusGeometry args={[1.72, 0.018, 8, 96]} />
        <meshBasicMaterial color={color} transparent opacity={0.76} />
      </mesh>
      <mesh rotation={[0.2, Math.PI / 2.2, 0]}>
        <torusGeometry args={[1.64, 0.014, 8, 96]} />
        <meshBasicMaterial color="#38BDF8" transparent opacity={0.72} />
      </mesh>
      <mesh rotation={[Math.PI / 2, 0.3, 0.38]}>
        <torusGeometry args={[1.52, 0.012, 8, 96]} />
        <meshBasicMaterial color="#E2E8F0" transparent opacity={0.5} />
      </mesh>
      {[
        [-1.12, 0.42, 0.56],
        [0.72, 1.02, -0.5],
        [1.03, -0.46, 0.62],
        [-0.38, -1.08, -0.42],
      ].map(([x, y, z], index) => (
        <mesh key={index} position={[x, y, z]}>
          <sphereGeometry args={[0.07, 12, 12]} />
          <meshBasicMaterial color={index % 2 ? '#38BDF8' : color} />
        </mesh>
      ))}
    </group>
  );
};

export const ThreeDOrbitalScene: React.FC<{ color?: string; sceneIndex?: number }> = ({
  color = '#D4AF37',
  sceneIndex = 0,
}) => {
  const { width } = useVideoConfig();
  const canvasW = Math.min(width - 100, 820);

  return (
    <div style={{ width: canvasW, height: 420, margin: '18px auto 0 auto' }}>
      <ThreeCanvas width={canvasW} height={420} camera={{ fov: 44, position: [0, 0.5, 5.5] }}>
        <ambientLight intensity={0.7} />
        <pointLight position={[5, 6, 5]} intensity={2.6} color={color} />
        <pointLight position={[-5, -4, 4]} intensity={1.8} color="#38BDF8" />
        <NetworkCore color={color} phase={sceneIndex * 0.52} />
      </ThreeCanvas>
    </div>
  );
};

const BarsMesh: React.FC<{
  bars: { label: string; value: number }[];
  color: string;
  phase: number;
}> = ({ bars, color, phase }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const maxVal = Math.max(...bars.map((b) => b.value), 1);

  return (
    <group position={[0, -1.25, 0]} rotation={[0.18, Math.sin(frame / 42 + phase) * 0.22, phase]}>
      {bars.map((b, i) => {
        const grow = spring({
          frame: Math.max(0, frame - i * 6),
          fps,
          config: { damping: 13, stiffness: 95 },
        });
        const height = Math.max(0.28, (b.value / maxVal) * 2.7 * grow);
        const xPos = (i - (bars.length - 1) / 2) * 1.18;
        const isPeak = i === bars.length - 1;
        return (
          <mesh key={i} position={[xPos, height / 2, 0]}>
            <boxGeometry args={[0.74, height, 0.74]} />
            <meshStandardMaterial
              color={isPeak ? color : '#1E293B'}
              metalness={0.78}
              roughness={0.2}
              emissive={isPeak ? color : '#38BDF8'}
              emissiveIntensity={isPeak ? 0.38 : 0.14}
            />
          </mesh>
        );
      })}
    </group>
  );
};

export const ThreeDBarChartScene: React.FC<{
  bars?: { label: string; value: number }[];
  color?: string;
  sceneIndex?: number;
}> = ({
  bars,
  color = '#D4AF37',
  sceneIndex = 0,
}) => {
  const { width } = useVideoConfig();
  const canvasW = Math.min(width - 100, 820);
  const hasData = Boolean(bars && bars.length > 0);
  const chartBars = bars?.length
    ? bars
    : Array.from({ length: 6 }, (_, index) => ({
        label: String(index + 1).padStart(2, '0'),
        value: 35 + ((sceneIndex * 23 + index * 29) % 64),
      }));

  return (
    <div style={{ width: canvasW, height: 390, margin: '14px auto 0 auto', position: 'relative' }}>
      {!hasData && (
        <div
          style={{
            position: 'absolute',
            top: 8,
            left: 18,
            zIndex: 2,
            color: '#CBD5E1',
            font: '700 13px "JetBrains Mono", monospace',
            letterSpacing: '0.12em',
          }}
        >
          ILLUSTRATIVE FORM · NOT LIVE DATA
        </div>
      )}
      <ThreeCanvas width={canvasW} height={390} camera={{ fov: 44, position: [0, 0.8, 5.2] }}>
        <ambientLight intensity={0.75} />
        <directionalLight position={[4, 7, 5]} intensity={2.5} color="#FFFFFF" />
        <pointLight position={[-4, 3, 4]} intensity={1.7} color={color} />
        <BarsMesh bars={chartBars} color={color} phase={sceneIndex * 0.41} />
      </ThreeCanvas>
      {hasData && (
        <div style={{ display: 'flex', justifyContent: 'space-around', padding: '0 40px', marginTop: -16 }}>
          {chartBars.map((bar, index) => (
            <div key={index} style={{ textAlign: 'center' }}>
              <div style={{ color: '#F8FAFC', fontSize: 25, fontWeight: 900 }}>{bar.value}</div>
              <div style={{ color: '#CBD5E1', fontSize: 20, fontWeight: 700 }}>{bar.label}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export const ThreeDScenes: React.FC<{
  sceneType: SceneType;
  themeColor: string;
  barValues?: { label: string; value: number }[];
  sceneIndex: number;
}> = ({ sceneType, themeColor, barValues, sceneIndex }) => {
  if (sceneType === 'three_d_globe') {
    return <ThreeDOrbitalScene color={themeColor} sceneIndex={sceneIndex} />;
  }

  if (sceneType === 'three_d_bars') {
    return <ThreeDBarChartScene bars={barValues} color={themeColor} sceneIndex={sceneIndex} />;
  }

  return null;
};
