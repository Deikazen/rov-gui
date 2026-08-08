import React, { useRef, useEffect, useCallback } from 'react';
import type { Point2D } from '../types/telemetry';
import { PanelWrapper } from './PanelWrapper';

interface TrajectoryPanelProps {
    rovPos: Point2D;
    recordedPath: Point2D[];
    trajPath: Point2D[];
    imuYaw: number;
    isReplaying: boolean;
    onReplay: () => void;
    onClear: () => void;
    theme: 'dark' | 'light';
}

export const TrajectoryPanel: React.FC<TrajectoryPanelProps> = ({
    rovPos,
    recordedPath,
    trajPath,
    imuYaw,
    isReplaying,
    onReplay,
    onClear,
    theme
}) => {
    const canvasRef = useRef<HTMLCanvasElement | null>(null);

    const resizeCanvas = useCallback(() => {
        const cvs = canvasRef.current;
        if (!cvs || !cvs.parentElement) return;
        const rect = cvs.parentElement.getBoundingClientRect();
        cvs.width = rect.width;
        cvs.height = rect.height;
    }, []);

    useEffect(() => {
        resizeCanvas();
        window.addEventListener('resize', resizeCanvas);
        window.addEventListener('rov-layout-change', resizeCanvas);
        return () => {
            window.removeEventListener('resize', resizeCanvas);
            window.removeEventListener('rov-layout-change', resizeCanvas);
        };
    }, [resizeCanvas]);

    useEffect(() => {
        const cvs = canvasRef.current;
        if (!cvs) return;
        const ctx = cvs.getContext('2d');
        if (!ctx) return;

        const W = cvs.width;
        const H = cvs.height;
        if (!W || !H) return;

        const isLight = theme === 'light';
        const mapBg = isLight ? '#f8fafc' : '#0b0e17';
        const gridColor = isLight ? 'rgba(148,163,184,0.42)' : 'rgba(30,37,56,0.5)';
        const labelColor = isLight ? '#475569' : '#64748b';

        ctx.clearRect(0, 0, W, H);
        ctx.fillStyle = mapBg;
        ctx.fillRect(0, 0, W, H);

        // Grid lines
        ctx.strokeStyle = gridColor;
        ctx.lineWidth = 1;
        const gridStep = 30;
        for (let x = 0; x < W; x += gridStep) { ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, H); ctx.stroke(); }
        for (let y = 0; y < H; y += gridStep) { ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(W, y); ctx.stroke(); }

        const mapToCanvas = (nx: number, ny: number) => {
            const pad = 20;
            return { x: pad + nx * (W - pad * 2), y: pad + ny * (H - pad * 2) };
        };

        // Start & End markers
        if (trajPath.length > 0) {
            const start = mapToCanvas(trajPath[0].x, trajPath[0].y);
            ctx.fillStyle = '#10b981';
            ctx.beginPath(); ctx.arc(start.x, start.y, 5, 0, Math.PI * 2); ctx.fill();

            const end = mapToCanvas(trajPath[trajPath.length - 1].x, trajPath[trajPath.length - 1].y);
            ctx.fillStyle = '#f43f5e';
            ctx.beginPath(); ctx.arc(end.x, end.y, 5, 0, Math.PI * 2); ctx.fill();
        }

        // Recorded path
        if (recordedPath.length > 1) {
            ctx.strokeStyle = '#f59e0b';
            ctx.lineWidth = 2;
            ctx.beginPath();
            const p0 = mapToCanvas(recordedPath[0].x, recordedPath[0].y);
            ctx.moveTo(p0.x, p0.y);
            for (let i = 1; i < recordedPath.length; i++) {
                const p = mapToCanvas(recordedPath[i].x, recordedPath[i].y);
                ctx.lineTo(p.x, p.y);
            }
            ctx.stroke();
        }

        // ROV position & heading
        const rov = mapToCanvas(rovPos.x, rovPos.y);
        const angle = (imuYaw - 90) * Math.PI / 180;

        ctx.save();
        ctx.translate(rov.x, rov.y);
        ctx.rotate(angle);
        ctx.fillStyle = '#00aaff';
        ctx.beginPath();
        ctx.moveTo(6, 0); ctx.lineTo(-4, 4); ctx.lineTo(-1, 0); ctx.lineTo(-4, -4);
        ctx.closePath(); ctx.fill();
        ctx.restore();

        ctx.fillStyle = labelColor;
        ctx.font = '9px monospace';
        ctx.textAlign = 'left';
        ctx.fillText(`X:${(rovPos.x * 10).toFixed(1)} Y:${(rovPos.y * 10).toFixed(1)}`, rov.x + 10, rov.y - 4);
    }, [rovPos, recordedPath, trajPath, imuYaw, theme]);

    const footer = (
        <div className="traj-panel-footer">
            <button
                className="action-btn"
                id="btn-replay"
                onClick={onReplay}
                style={{ color: isReplaying ? 'var(--amber)' : '' }}
            >
                {isReplaying ? 'Replaying...' : 'Replay Path'}
            </button>
            <button className="action-btn" id="btn-clear" onClick={onClear}>
                Clear
            </button>
        </div>
    );

    return (
        <PanelWrapper
            className="traj-panel"
            title="TRAJECTORY MAP — TOP-DOWN VIEW"
            footer={footer}
            onLayoutChange={resizeCanvas}
        >
            <canvas ref={canvasRef} id="traj-canvas" />
        </PanelWrapper>
    );
};
