import React, { useState } from "react";
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
  const [feedError, setFeedError] = useState(false);
  const [isContainFit, setIsContainFit] = useState(false);
  const hasStreamConfig = Boolean(streamUrl && streamUrl.trim().length > 0);
  const isLive = hasStreamConfig && !feedError;

  const handleRetryFeed = () => {
    setFeedError(false);
  };

  return (
    <PanelWrapper className="cam-panel" title={title}>
      <div className="cam-feed-wrap">
        {/* Live Stream / Simulation Background */}
        {isLive ? (
          <img
            className={`cam-feed-live ${isContainFit ? "contain" : "cover"}`}
            src={streamUrl}
            alt={title}
            onError={() => setFeedError(true)}
          />
        ) : (
          <div className={`cam-feed-bg ${poolClass}`} />
        )}

        {/* Offline Stream Notification Banner with Retry */}
        {hasStreamConfig && feedError && (
          <div className="cam-offline-banner">
            <div className="cam-offline-text">⚠️ STREAM OFFLINE / DISCONNECTED</div>
            <button
              type="button"
              className="cam-retry-btn"
              onClick={handleRetryFeed}
            >
              ↻ Reconnect Feed
            </button>
          </div>
        )}

        {/* Tactical Scanlines & Vignette */}
        <div className="cam-scanlines" />

        {/* Tactical Corner HUD Brackets */}
        <div className="cam-corner-brackets">
          <span className="bracket tl" />
          <span className="bracket tr" />
          <span className="bracket bl" />
          <span className="bracket br" />
        </div>

        {/* Aiming Reticle & Crosshairs */}
        <div className="cam-reticle-wrap">
          <div className="cam-reticle">
            <div className="cam-crosshair" />
            <div className="cam-crosshair-v" />
            <div className="cam-reticle-dot" />
          </div>
        </div>

        {/* Top HUD: Timestamp & Status Badges */}
        <div className="cam-top-hud">
          <div className="cam-timestamp">{timestamp}</div>
          <div className="cam-top-badges">
            <button
              type="button"
              className="cam-fit-toggle-btn"
              onClick={() => setIsContainFit((prev) => !prev)}
              title={isContainFit ? "Mode: Fit (Ubah ke Fill/Cover)" : "Mode: Fill (Ubah ke Fit/Contain)"}
            >
              {isContainFit ? "FIT" : "FILL"}
            </button>
            {isLive ? (
              <div className="cam-badge-live">
                <span className="cam-live-dot" />
                LIVE
              </div>
            ) : (
              <div className="cam-badge-sim">
                <span className="cam-sim-dot" />
                SIM
              </div>
            )}
            <div className="cam-badge-rec">
              <span className="cam-rec-dot" />
              REC
            </div>
          </div>
        </div>

        {/* Bottom HUD: Label & Controls */}
        <div className="cam-bottom-hud">
          <div className="cam-label-overlay">{overlayLabel}</div>

          <div className="cam-bottom-controls">
            {!isLive ? (
              <div className="cam-timeline">
                <button
                  className="cam-play-btn"
                  type="button"
                  onClick={() => onTogglePlay(id)}
                  title={cameraState.playing ? "Pause Replay" : "Play Replay"}
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
                  title="Timeline scrubber"
                />
                <div className="cam-timecode">
                  {formatVideoTime(cameraState.time)} /{" "}
                  {formatVideoTime(cameraState.duration)}
                </div>
              </div>
            ) : (
              <div className="cam-live-telemetry">
                <span className="cam-live-tag">MJPEG STREAM</span>
              </div>
            )}
          </div>
        </div>
      </div>
    </PanelWrapper>
  );
};
