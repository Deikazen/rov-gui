import React from "react";
import type { CameraState } from "../types/telemetry";
import { PanelWrapper } from "./PanelWrapper";

interface CameraPanelProps {
  id: number;
  title: string;
  poolClass: string;
  overlayLabel: string;
  timestamp: string;
  cameraState: CameraState;
  onTogglePlay: (id: number) => void;
  onSeek: (id: number, percent: number) => void;
  /** URL MJPEG stream dari backend (mis. http://192.168.x.x:9010/video_feed). Kosongkan untuk fallback simulasi. */
  streamUrl?: string;
}

function formatVideoTime(seconds: number): string {
  const safe = Math.max(0, Math.floor(seconds));
  return `${String(Math.floor(safe / 60)).padStart(2, "0")}:${String(safe % 60).padStart(2, "0")}`;
}

export const CameraPanel: React.FC<CameraPanelProps> = ({
  id,
  title,
  poolClass,
  overlayLabel,
  timestamp,
  cameraState,
  onTogglePlay,
  onSeek,
  streamUrl,
}) => {
  const sliderVal = String((cameraState.time / cameraState.duration) * 100);
  const [feedError, setFeedError] = React.useState(false);
  const isLive = Boolean(streamUrl) && !feedError;

  return (
    <PanelWrapper className="cam-panel" title={title}>
      {isLive ? (
        <img
          className="cam-feed-live"
          src={streamUrl}
          alt={title}
          onError={() => setFeedError(true)}
        />
      ) : (
        <div className={`cam-feed-bg ${poolClass}`}>
          <div className="cam-reticle">
            <div className="cam-crosshair"></div>
            <div className="cam-crosshair-v"></div>
          </div>
        </div>
      )}
      <div className="cam-timestamp">{timestamp}</div>
      <div className="cam-rec">
        <div className="cam-rec-dot"></div>REC
      </div>
      <div className="cam-timeline">
        <button
          className="cam-play-btn"
          type="button"
          onClick={() => onTogglePlay(id)}
        >
          {cameraState.playing ? "II" : "▶"}
        </button>
        <input
          className="cam-slider"
          type="range"
          min="0"
          max="100"
          value={sliderVal}
          onInput={(e) => onSeek(id, Number(e.currentTarget.value))}
        />
        <div className="cam-timecode">
          {formatVideoTime(cameraState.time)} /{" "}
          {formatVideoTime(cameraState.duration)}
        </div>
      </div>
      <div className="cam-label-overlay">{overlayLabel}</div>
    </PanelWrapper>
  );
};
