import React, { useState, useRef } from "react";
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

  // Zoom & Pan state
  const [zoom, setZoom] = useState(1.0);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const dragStartRef = useRef({ x: 0, y: 0 });

  const hasStreamConfig = Boolean(streamUrl && streamUrl.trim().length > 0);
  const isLive = hasStreamConfig && !feedError;

  // Listen to Global Reset Layout Event
  React.useEffect(() => {
    const handleGlobalReset = () => {
      setZoom(1.0);
      setPan({ x: 0, y: 0 });
      setIsContainFit(false);
    };
    window.addEventListener("rov-reset-layout", handleGlobalReset);
    return () => window.removeEventListener("rov-reset-layout", handleGlobalReset);
  }, []);

  const handleRetryFeed = () => {
    setFeedError(false);
  };

  const handleZoomIn = (e?: React.MouseEvent) => {
    if (e) e.stopPropagation();
    setZoom((prev) => Math.min(4.0, Math.round((prev + 0.25) * 100) / 100));
  };

  const handleZoomOut = (e?: React.MouseEvent) => {
    if (e) e.stopPropagation();
    setZoom((prev) => {
      const next = Math.max(1.0, Math.round((prev - 0.25) * 100) / 100);
      if (next === 1.0) setPan({ x: 0, y: 0 });
      return next;
    });
  };

  const handleResetZoom = (e?: React.MouseEvent) => {
    if (e) e.stopPropagation();
    setZoom(1.0);
    setPan({ x: 0, y: 0 });
  };

  const handleWheel = (e: React.WheelEvent) => {
    // Zoom in on scroll up, zoom out on scroll down
    const delta = e.deltaY < 0 ? 0.2 : -0.2;
    setZoom((prev) => {
      const next = Math.min(4.0, Math.max(1.0, Math.round((prev + delta) * 100) / 100));
      if (next === 1.0) setPan({ x: 0, y: 0 });
      return next;
    });
  };

  const handleMouseDown = (e: React.MouseEvent) => {
    if (zoom <= 1.0) return;
    if ((e.target as HTMLElement).closest("button, input, .cam-top-hud, .cam-bottom-hud, .cam-offline-banner")) {
      return;
    }
    setIsDragging(true);
    dragStartRef.current = { x: e.clientX - pan.x, y: e.clientY - pan.y };
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (!isDragging || zoom <= 1.0) return;
    setPan({
      x: e.clientX - dragStartRef.current.x,
      y: e.clientY - dragStartRef.current.y,
    });
  };

  const handleMouseUp = () => {
    setIsDragging(false);
  };

  const handleDoubleClick = (e: React.MouseEvent) => {
    if ((e.target as HTMLElement).closest("button, input, .cam-top-hud, .cam-bottom-hud, .cam-offline-banner")) {
      return;
    }
    handleResetZoom();
  };

  return (
    <PanelWrapper className="cam-panel" title={title}>
      <div
        className={`cam-feed-wrap ${zoom > 1.0 ? "is-zoomed" : ""} ${isDragging ? "is-dragging" : ""}`}
        onWheel={handleWheel}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
        onDoubleClick={handleDoubleClick}
      >
        {/* Transformable Media Feed Layer */}
        <div
          className="cam-feed-media"
          style={{
            transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`,
            transformOrigin: "center center",
            transition: isDragging ? "none" : "transform 0.12s ease-out",
          }}
        >
          {isLive ? (
            <img
              className={`cam-feed-live ${isContainFit ? "contain" : "cover"}`}
              src={streamUrl}
              alt={title}
              onError={() => setFeedError(true)}
              draggable={false}
            />
          ) : (
            <div className={`cam-feed-bg ${poolClass}`} />
          )}
        </div>

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

        {/* Top HUD: Timestamp, Zoom Controls & Status Badges */}
        <div className="cam-top-hud">
          <div className="cam-timestamp">{timestamp}</div>

          <div className="cam-top-badges">
            {/* Zoom Controls: Zoom Out (-), Current Zoom / Reset Click, Zoom In (+) */}
            <div className="cam-zoom-controls" title="Zoom kamera (atau scroll mouse di layar)">
              <button
                type="button"
                className="cam-zoom-btn"
                onClick={handleZoomIn}
                disabled={zoom >= 4.0}
                title="Perbesar (+)"
              >
                +
              </button>
              <button
                type="button"
                className={`cam-zoom-badge ${zoom > 1.0 ? "active" : ""}`}
                onClick={handleResetZoom}
                title="Klik untuk Reset ke ukuran awal (1.0x)"
              >
                {zoom.toFixed(1)}x
              </button>
              <button
                type="button"
                className="cam-zoom-btn"
                onClick={handleZoomOut}
                disabled={zoom <= 1.0}
                title="Perkecil (−)"
              >
                −
              </button>
            </div>

            {/* Tombol Reset jika sedang di-zoom */}
            {zoom > 1.0 && (
              <button
                type="button"
                className="cam-zoom-reset-btn"
                onClick={handleResetZoom}
                title="Reset zoom & posisi ke ukuran awal"
              >
                ↺ Reset
              </button>
            )}

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
