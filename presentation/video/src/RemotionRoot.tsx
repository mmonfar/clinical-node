import React from "react";
import { Composition } from "remotion";
import { HODCommittee } from "./Root";
import { FPS, TOTAL_FRAMES } from "./constants";

export const RemotionRoot: React.FC = () => {
  return (
    <Composition
      id="HODCommittee"
      component={HODCommittee}
      durationInFrames={TOTAL_FRAMES}
      fps={FPS}
      width={1920}
      height={1080}
    />
  );
};
