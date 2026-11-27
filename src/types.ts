export type SceneType =
  | 'cinema_hero'
  | 'three_d_globe'
  | 'three_d_bars'
  | 'candlestick_chart'
  | 'split_compare'
  | 'step_list'
  | 'cinema_outro'
  | 'kinetic_type'
  | 'process_diagram'
  | 'editorial_montage'
  | 'data_viz';

export type CameraMotion = 'zoom_in' | 'zoom_out' | 'pan_left' | 'pan_right' | 'dolly_push';

export interface SceneItem {
  type: SceneType;
  startSec: number;
  endSec: number;
  kicker: string;
  headline: string;
  subline?: string;
  statValue?: string;
  bullets?: string[];
  leftLabel?: string;
  rightLabel?: string;
  barValues?: { label: string; value: number }[];
  visualQuery?: string;
  mediaFile?: string;
  mediaKind?: 'video' | 'image' | 'none';
  cameraMotion?: CameraMotion;
  sfxCue?: 'boom' | 'whoosh' | 'riser' | 'pulse';
  accentColor?: string;
}

export interface WordTiming {
  word: string;
  start: number;
  end: number;
}

export interface VideoProps extends Record<string, unknown> {
  title: string;
  brandTag: string;
  themeColor: string;
  mode: 'cinema' | 'shorts';
  format?: 'vertical' | 'landscape';
  viralMode?: 'phonk' | 'meme' | 'cinema' | 'newsroom' | 'commercial' | 'explainer' | 'travel' | 'story' | 'technology' | 'editorial';
  beatSync?: boolean;
  beatTimestamps?: number[];
  totalDurationSec: number;
  scenes: SceneItem[];
  words: WordTiming[];
  voiceoverFile?: string;
  ambientScoreFile?: string;
  masterAudioFile?: string;
  sfxBoomFile?: string;
  sfxWhooshFile?: string;
  sfxPopFile?: string;
  sfxFiles?: Partial<Record<'boom' | 'whoosh' | 'pulse', string[]>>;
  isLandscape?: boolean;
}
