import React, { useMemo } from 'react';
import { ThreeCanvas } from '@remotion/three';
import { spring, useCurrentFrame, useVideoConfig } from 'remotion';
import * as THREE from 'three';
import type { SceneType } from '../types';

const CinemaCore: React.FC<{ color: string }> = ({ color }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const scale = spring({ frame, fps, config: { damping: 14, stiffness: 85 } });
  const rotY = (frame / fps) * 0.85;
  const rotX = Math.sin(frame / 28) * 0.22;

  const ringPoints = useMemo(() => {
    const pts: THREE.Vector3[] = [];
    for (let i = 0; i <= 96; i++) {
      const a = (i / 96) * Math.PI * 2;
      pts.push(new THREE.Vector3(Math.cos(a) * 2.5, Math.sin(a * 2) * 0.22, Math.sin(a) * 2.5));
    }
    return pts;
  }, []);

  const ringGeo = useMemo(() => new THREE.BufferGeometry().setFromPoints(ringPoints), [ringPoints]);
  const ringLine = useMemo(
    () => new THREE.Line(ringGeo, new THREE.LineBasicMaterial({ color: '#38BDF8' })),
    [ringGeo]
  );

  return (
    <group scale={scale} rotation={[rotX, rotY, 0.14]}>
      <mesh>
        <icosahedronGeometry args={[1.38, 1]} />
        <meshStandardMaterial
          color="#090D16"
          metalness={0.9}
          roughness={0.18}
          emissive={color}
          emissiveIntensity={0.28}
        />
      </mesh>
      <mesh>
        <icosahedronGeometry args={[1.6, 2]} />
        <meshBasicMaterial color={color} wireframe transparent opacity={0.7} />
      </mesh>
      <mesh rotation={[Math.PI / 2.4, 0, 0]}>
        <torusGeometry args={[2.1, 0.025, 16, 100]} />
        <meshStandardMaterial color={color} emissive={color} emissiveIntensity={0.6} />
      </mesh>
      <primitive object={ringLine} />
    </group>
  );
};

export const ThreeDOrbitalScene: React.FC<{ color?: string }> = ({ color = '#D4AF37' }) => {
  const { width } = useVideoConfig();
  const canvasW = Math.min(width - 100, 820);

  return (
    <div style={{ width: canvasW, height: 420, margin: '18px auto 0 auto' }}>
      <ThreeCanvas width={canvasW} height={420} camera={{ fov: 44, position: [0, 0.5, 5.5] }}>
        <ambientLight intensity={0.7} />
        <pointLight position={[5, 6, 5]} intensity={2.6} color={color} />
        <pointLight position={[-5, -4, 4]} intensity={1.8} color="#38BDF8" />
        <CinemaCore color={color} />
      </ThreeCanvas>
    </div>
  );
};

const BarsMesh: React.FC<{ bars: { label: string; value: number }[]; color: string }> = ({ bars, color }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const maxVal = Math.max(...bars.map((b) => b.value), 1);

  return (
    <group position={[0, -1.25, 0]} rotation={[0.18, Math.sin(frame / 42) * 0.22, 0]}>
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
}> = ({
  bars = [
    { label: 'Q1', value: 28 },
    { label: 'Q2', value: 49 },
    { label: 'Q3', value: 72 },
    { label: 'Q4', value: 98 },
  ],
  color = '#D4AF37',
}) => {
  const { width } = useVideoConfig();
  const canvasW = Math.min(width - 100, 820);

  return (
    <div style={{ width: canvasW, height: 390, margin: '14px auto 0 auto' }}>
      <ThreeCanvas width={canvasW} height={390} camera={{ fov: 44, position: [0, 0.8, 5.2] }}>
        <ambientLight intensity={0.75} />
        <directionalLight position={[4, 7, 5]} intensity={2.5} color="#FFFFFF" />
        <pointLight position={[-4, 3, 4]} intensity={1.7} color={color} />
        <BarsMesh bars={bars} color={color} />
      </ThreeCanvas>
      <div style={{ display: 'flex', justifyContent: 'space-around', padding: '0 40px', marginTop: -16 }}>
        {bars.map((b, i) => (
          <div key={i} style={{ textAlign: 'center' }}>
            <div style={{ color: '#F8FAFC', fontSize: 25, fontWeight: 900 }}>{b.value}</div>
            <div style={{ color: '#CBD5E1', fontSize: 20, fontWeight: 700 }}>{b.label}</div>
          </div>
        ))}
      </div>
    </div>
  );
};

export const ThreeDScenes: React.FC<{
  sceneType: SceneType;
  themeColor: string;
  barValues?: { label: string; value: number }[];
}> = ({ sceneType, themeColor, barValues }) => {
  if (sceneType === 'three_d_globe') {
    return <ThreeDOrbitalScene color={themeColor} />;
  }

  if (sceneType === 'three_d_bars' || sceneType === 'candlestick_chart') {
    return <ThreeDBarChartScene bars={barValues} color={themeColor} />;
  }

  return null;
};
