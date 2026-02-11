import React from "react";
import { Composition } from "remotion";
import { AIBomDemo } from "./AIBomDemo";
import { N8nDemo } from "./N8nDemo";

export const Root: React.FC = () => {
  return (
    <>
      <Composition
        id="AIBomDemo"
        component={AIBomDemo}
        durationInFrames={540}
        fps={30}
        width={800}
        height={500}
      />
      <Composition
        id="N8nDemo"
        component={N8nDemo}
        durationInFrames={450}
        fps={30}
        width={800}
        height={500}
      />
    </>
  );
};
