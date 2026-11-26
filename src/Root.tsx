import React from 'react';
import { Composition, type AnyZodObject } from 'remotion';
import { MainVideo } from './MainVideo';
import { VideoProps } from './types';
import videoData from '../public/video_data.json';

export const RemotionRoot: React.FC = () => {
  const props = videoData as VideoProps;
  const fps = 30;
  const durationInFrames = Math.max(90, Math.ceil((props.totalDurationSec || 15) * fps));

  return (
    <>
      <Composition<AnyZodObject, VideoProps>
        id="MainComp"
        component={MainVideo}
        durationInFrames={durationInFrames}
        fps={fps}
        width={1080}
        height={1920}
        defaultProps={{ ...props, isLandscape: false }}
      />
      <Composition<AnyZodObject, VideoProps>
        id="LandscapeComp"
        component={MainVideo}
        durationInFrames={durationInFrames}
        fps={fps}
        width={1920}
        height={1080}
        defaultProps={{ ...props, isLandscape: true }}
      />
    </>
  );
};
