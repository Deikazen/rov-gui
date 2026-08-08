import React from 'react';
import type { CameraState } from '../types/telemetry';
import { PanelWrapper } from './PanelWrapper';

interface CameraPanelProps {
    id: number;
    title: string;
    poolClass: string;
    overlayLabel: string;
    timestamp: string;
    cameraState: CameraState;
    onTogglePlay: (id: number) => void;
    onSeek: (id: number, percent: number) => void;
}

function formatVideoTime(seconds: number): string {
    const safe = Math.max(0, Math.floor(seconds));
    return `${String(Math.floor(safe / 60)).padStart(2, '0')}:${String(safe % 60).padStart(2, '0')}`;
}

export const CameraPanel: React.FC<CameraPanelProps> = ({
    id,
    title,
    poolClass,
    overlayLabel,
    timestamp,
    cameraState,
    onTogglePlay,
    onSeek
}) => {
    const sliderVal = String((cameraState.time / cameraState.duration) * 100);

    return (
        <PanelWrapper className="cam-panel" title={title}>
            <div className={`cam-feed-bg ${poolClass}`}>
                <div className="cam-reticle">
                    <div className="cam-crosshair"></div>
                    <div className="cam-crosshair-v"></div>
                </div>
            </div>
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
                    {cameraState.playing ? 'II' : '▶'}
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
                    {formatVideoTime(cameraState.time)} / {formatVideoTime(cameraState.duration)}
                </div>
            </div>
            <div className="cam-label-overlay">{overlayLabel}</div>
        </PanelWrapper>
    );
};
