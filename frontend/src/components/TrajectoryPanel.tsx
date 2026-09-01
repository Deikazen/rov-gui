import React, { useRef, useEffect, useState, useCallback } from 'react';
import type { Point2D, TrajectoryTelemetry } from '../types/telemetry';
import { PanelWrapper } from './PanelWrapper';

interface TrajectoryPanelProps {
    rovPos?: Point2D;
    recordedPath?: Point2D[];
    trajPath?: Point2D[];
    imuYaw?: number;
    isReplaying?: boolean;
    onReplay?: () => void;
    onClear?: () => void;
    theme?: 'dark' | 'light';
}

export const TrajectoryPanel: React.FC<TrajectoryPanelProps> = ({
    rovPos: fallbackPos = { x: 0, y: 0 },
    imuYaw: fallbackYaw = 0,
    theme = 'dark',
}) => {
    const canvasRef = useRef<HTMLCanvasElement | null>(null);

    // Backend Telemetry State dari /api/trajectory (port 8007)
    const [telemetry, setTelemetry] = useState<TrajectoryTelemetry>({
        source: 'dummy',
        x: 0,
        y: 0,
        z: 0,
        raw_x: 0,
        raw_y: 0,
        raw_z: 0,
        origin_x: 0,
        origin_y: 0,
        origin_z: 0,
        yaw: 0,
        mavlink_connected: false,
    });

    const [isBackendConnected, setIsBackendConnected] = useState<boolean>(false);
    const [livePath, setLivePath] = useState<Point2D[]>([]);
    const [zoomScale, setZoomScale] = useState<number>(45); // pixels per meter (default: 45px = 1m)
    const [autoCenter, setAutoCenter] = useState<boolean>(true);
    const [panOffset, setPanOffset] = useState<Point2D>({ x: 0, y: 0 });
    const [isDragging, setIsDragging] = useState<boolean>(false);
    const [dragStart, setDragStart] = useState<Point2D>({ x: 0, y: 0 });
    const [toastMessage, setToastMessage] = useState<string | null>(null);
    const [isCalibrating, setIsCalibrating] = useState<boolean>(false);

    const toastTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

    const showToast = useCallback((msg: string) => {
        if (toastTimeoutRef.current) clearTimeout(toastTimeoutRef.current);
        setToastMessage(msg);
        toastTimeoutRef.current = setTimeout(() => {
            setToastMessage(null);
        }, 2800);
    }, []);

    // 1. Fetch data dari Flask backend (http://localhost:8007/api/trajectory) setiap 100ms (10 Hz)
    useEffect(() => {
        let isMounted = true;
        let isFetching = false;
        let failureCount = 0;

        const fetchTrajectory = async () => {
            // Cegah request overlap jika request sebelumnya belum selesai
            if (isFetching) return;
            isFetching = true;

            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 1500);

            try {
                const res = await fetch('http://localhost:8007/api/trajectory', {
                    signal: controller.signal,
                });
                clearTimeout(timeoutId);

                if (!res.ok) {
                    throw new Error(`HTTP error! status: ${res.status}`);
                }

                const data: TrajectoryTelemetry = await res.json();
                if (!isMounted) return;

                failureCount = 0;
                setIsBackendConnected(true);
                setTelemetry(data);

                // Update trajectory breadcrumbs
                setLivePath((prev) => {
                    const last = prev[prev.length - 1];
                    const currentPt = { x: data.x, y: data.y };
                    // Catat titik jika bergerak lebih dari 3cm
                    if (!last || Math.hypot(data.x - last.x, data.y - last.y) > 0.03) {
                        const updated = [...prev, currentPt];
                        return updated.length > 1200 ? updated.slice(updated.length - 1200) : updated;
                    }
                    return prev;
                });
            } catch {
                clearTimeout(timeoutId);
                if (isMounted) {
                    failureCount++;
                    // Hanya tandai OFFLINE jika gagal 5x berturut-turut untuk mencegah flickering
                    if (failureCount >= 5) {
                        setIsBackendConnected(false);
                    }
                }
            } finally {
                isFetching = false;
            }
        };

        const interval = setInterval(fetchTrajectory, 100);
        return () => {
            isMounted = false;
            clearInterval(interval);
        };
    }, []);

    // 2. Tombol Kalibrasi Titik Origin ke Backend
    const handleCalibrateOrigin = async () => {
        setIsCalibrating(true);
        try {
            const res = await fetch('http://localhost:8007/api/origin/calibrate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
            });
            if (res.ok) {
                const resData = await res.json();
                showToast(`✓ Origin Dikalibrasi ke Posisi Saat Ini: (X:${resData.origin.x}m, Y:${resData.origin.y}m)`);
                // Clear recent path agar path dimulai ulang dari titik origin baru
                setLivePath([{ x: 0, y: 0 }]);
                if (autoCenter) setPanOffset({ x: 0, y: 0 });
            } else {
                showToast('❌ Gagal mengalibrasi origin ke server');
            }
        } catch {
            showToast('⚠️ Backend Offline: Origin di-set ke (0,0) lokal');
            setLivePath([{ x: 0, y: 0 }]);
        } finally {
            setIsCalibrating(false);
        }
    };

    // 3. Tombol Reset Origin ke Default (0,0,0)
    const handleResetOrigin = async () => {
        try {
            const res = await fetch('http://localhost:8007/api/origin/reset', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
            });
            if (res.ok) {
                showToast('↺ Origin Di-reset ke Default (0, 0)');
                setLivePath([]);
            }
        } catch {
            showToast('⚠️ Backend Offline: Reset lokal');
            setLivePath([]);
        }
    };

    // 4. Toggle Sumber Data (REAL Pixhawk / DUMMY Simulation)
    const toggleSource = async () => {
        const nextSource = telemetry.source === 'real' ? 'dummy' : 'real';
        // Optimistic UI update agar tombol langsung merespons seketika
        setTelemetry((prev) => ({ ...prev, source: nextSource }));
        try {
            await fetch('http://localhost:8007/api/source', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ source: nextSource }),
            });
            showToast(`Mode Sumber Data: ${nextSource.toUpperCase()}`);
        } catch {
            showToast('⚠️ Gagal mengubah source: Server offline');
        }
    };

    // 5. Clear Trajectory History
    const handleClearPath = () => {
        setLivePath([]);
        showToast('🗑 Jejak Trajectory Dibersihkan');
    };

    // 6. Penanganan Resize Canvas (Fix canvas feedback loop)
    const resizeCanvas = useCallback(() => {
        const cvs = canvasRef.current;
        if (!cvs || !cvs.parentElement) return;
        const rect = cvs.parentElement.getBoundingClientRect();
        const dpr = window.devicePixelRatio || 1;
        const w = Math.floor(rect.width);
        const h = Math.floor(rect.height);
        if (w > 0 && h > 0) {
            cvs.width = w * dpr;
            cvs.height = h * dpr;
        }
    }, []);

    useEffect(() => {
        resizeCanvas();
        const handleGlobalReset = () => {
            setZoomScale(45);
            setPanOffset({ x: 0, y: 0 });
            setAutoCenter(true);
            resizeCanvas();
        };
        window.addEventListener('resize', resizeCanvas);
        window.addEventListener('rov-layout-change', resizeCanvas);
        window.addEventListener('rov-reset-layout', handleGlobalReset);
        return () => {
            window.removeEventListener('resize', resizeCanvas);
            window.removeEventListener('rov-layout-change', resizeCanvas);
            window.removeEventListener('rov-reset-layout', handleGlobalReset);
        };
    }, [resizeCanvas]);

    // 7. Mouse Pan & Zoom Interactivity
    const handleMouseDown = (e: React.MouseEvent<HTMLCanvasElement>) => {
        setIsDragging(true);
        setDragStart({ x: e.clientX - panOffset.x, y: e.clientY - panOffset.y });
    };

    const handleMouseMove = (e: React.MouseEvent<HTMLCanvasElement>) => {
        if (!isDragging) return;
        setAutoCenter(false);
        setPanOffset({
            x: e.clientX - dragStart.x,
            y: e.clientY - dragStart.y,
        });
    };

    const handleMouseUp = () => {
        setIsDragging(false);
    };

    const handleWheel = (e: React.WheelEvent<HTMLCanvasElement>) => {
        e.preventDefault();
        const zoomFactor = e.deltaY < 0 ? 1.15 : 0.85;
        setZoomScale((prev) => Math.min(180, Math.max(15, prev * zoomFactor)));
    };

    // 8. Render Canvas Loop
    useEffect(() => {
        const cvs = canvasRef.current;
        if (!cvs) return;
        const ctx = cvs.getContext('2d');
        if (!ctx) return;

        const dpr = window.devicePixelRatio || 1;
        const W = cvs.width / dpr;
        const H = cvs.height / dpr;
        if (!W || !H) return;

        ctx.save();
        ctx.scale(dpr, dpr);

        const isLight = theme === 'light';
        const mapBg = isLight ? '#f8fafc' : '#080b11';
        const majorGridColor = isLight ? 'rgba(148, 163, 184, 0.5)' : 'rgba(30, 41, 59, 0.7)';
        const minorGridColor = isLight ? 'rgba(226, 232, 240, 0.6)' : 'rgba(15, 23, 42, 0.4)';
        const axisColor = isLight ? 'rgba(71, 85, 105, 0.7)' : 'rgba(56, 189, 248, 0.35)';
        const labelColor = isLight ? '#475569' : '#64748b';

        // Clear canvas
        ctx.clearRect(0, 0, W, H);
        ctx.fillStyle = mapBg;
        ctx.fillRect(0, 0, W, H);

        // Posisi ROV saat ini (dari backend atau fallback)
        const curX = isBackendConnected ? telemetry.x : fallbackPos.x;
        const curY = isBackendConnected ? telemetry.y : fallbackPos.y;
        const curYaw = isBackendConnected ? telemetry.yaw : fallbackYaw;

        // Center calculation
        const originScreenX = W / 2 + (autoCenter ? -curX * zoomScale : panOffset.x);
        const originScreenY = H / 2 + (autoCenter ? curY * zoomScale : panOffset.y);

        // Helper: konversi meter dunia (X kanan, Y atas) ke koordinat layar
        const worldToScreen = (wx: number, wy: number) => ({
            x: originScreenX + wx * zoomScale,
            y: originScreenY - wy * zoomScale, // Y-axis inverted in canvas
        });

        // ── A. DRAW METRIC GRID ──
        const meterStep = zoomScale > 70 ? 0.5 : zoomScale < 25 ? 2.0 : 1.0;
        const screenStep = meterStep * zoomScale;

        // Vertical Grid Lines
        const startX = originScreenX % screenStep;
        for (let x = startX; x < W; x += screenStep) {
            const worldVal = (x - originScreenX) / zoomScale;
            const isAxis = Math.abs(worldVal) < 0.01;
            ctx.strokeStyle = isAxis ? axisColor : Math.round(worldVal / meterStep) % 2 === 0 ? majorGridColor : minorGridColor;
            ctx.lineWidth = isAxis ? 1.5 : 1;
            ctx.beginPath();
            ctx.moveTo(x, 0);
            ctx.lineTo(x, H);
            ctx.stroke();

            // Label meter di sumbu X
            if (!isAxis && Math.abs(worldVal) >= 0.4) {
                ctx.fillStyle = labelColor;
                ctx.font = '9px monospace';
                ctx.textAlign = 'center';
                ctx.fillText(`${worldVal > 0 ? '+' : ''}${worldVal.toFixed(1)}m`, x, Math.min(H - 6, Math.max(14, originScreenY + 12)));
            }
        }

        // Horizontal Grid Lines
        const startY = originScreenY % screenStep;
        for (let y = startY; y < H; y += screenStep) {
            const worldVal = (originScreenY - y) / zoomScale;
            const isAxis = Math.abs(worldVal) < 0.01;
            ctx.strokeStyle = isAxis ? axisColor : Math.round(worldVal / meterStep) % 2 === 0 ? majorGridColor : minorGridColor;
            ctx.lineWidth = isAxis ? 1.5 : 1;
            ctx.beginPath();
            ctx.moveTo(0, y);
            ctx.lineTo(W, y);
            ctx.stroke();

            // Label meter di sumbu Y
            if (!isAxis && Math.abs(worldVal) >= 0.4) {
                ctx.fillStyle = labelColor;
                ctx.font = '9px monospace';
                ctx.textAlign = 'left';
                ctx.fillText(`${worldVal > 0 ? '+' : ''}${worldVal.toFixed(1)}m`, Math.min(W - 40, Math.max(6, originScreenX + 6)), y - 3);
            }
        }

        // ── B. DRAW ORIGIN POINT (0, 0) ──
        const originPos = worldToScreen(0, 0);
        // Outer pulsing ring
        ctx.strokeStyle = 'rgba(0, 240, 255, 0.4)';
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        ctx.arc(originPos.x, originPos.y, 14, 0, Math.PI * 2);
        ctx.stroke();

        // Inner crosshair
        ctx.strokeStyle = '#00f0ff';
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        ctx.moveTo(originPos.x - 8, originPos.y);
        ctx.lineTo(originPos.x + 8, originPos.y);
        ctx.moveTo(originPos.x, originPos.y - 8);
        ctx.lineTo(originPos.x, originPos.y + 8);
        ctx.stroke();

        // Center origin dot
        ctx.fillStyle = '#00f0ff';
        ctx.beginPath();
        ctx.arc(originPos.x, originPos.y, 3, 0, Math.PI * 2);
        ctx.fill();

        // Origin label
        ctx.fillStyle = '#00f0ff';
        ctx.font = 'bold 9px "JetBrains Mono", monospace';
        ctx.textAlign = 'left';
        ctx.fillText('ORIGIN (0,0)', originPos.x + 12, originPos.y - 10);

        // ── C. DRAW RECORDED TRAJECTORY PATH ──
        if (livePath.length > 1) {
            ctx.shadowBlur = 8;
            ctx.shadowColor = 'rgba(0, 170, 255, 0.5)';
            ctx.lineWidth = 2.5;

            // Gradient trail dari Cyan ke Amber
            for (let i = 1; i < livePath.length; i++) {
                const p0 = worldToScreen(livePath[i - 1].x, livePath[i - 1].y);
                const p1 = worldToScreen(livePath[i].x, livePath[i].y);
                const alpha = Math.min(1, 0.2 + (i / livePath.length) * 0.8);

                ctx.strokeStyle = `rgba(0, 210, 255, ${alpha})`;
                ctx.beginPath();
                ctx.moveTo(p0.x, p0.y);
                ctx.lineTo(p1.x, p1.y);
                ctx.stroke();
            }
            ctx.shadowBlur = 0;

            // Titik awal lintasan (Start Point - Emerald Green)
            const startPt = worldToScreen(livePath[0].x, livePath[0].y);
            ctx.fillStyle = '#10b981';
            ctx.beginPath();
            ctx.arc(startPt.x, startPt.y, 4.5, 0, Math.PI * 2);
            ctx.fill();
        }

        // ── D. DRAW REAL-TIME ROV GLYPH & HEADING ──
        const rovScreen = worldToScreen(curX, curY);

        // Beam / Vision Cone
        const radYaw = ((90 - curYaw) * Math.PI) / 180; // Standard math angle
        const coneDist = 32;
        const coneAngle = Math.PI / 5;

        ctx.save();
        ctx.translate(rovScreen.x, rovScreen.y);
        ctx.rotate(-radYaw + Math.PI / 2);

        // Sinar Lampu Depan (Headlight Cone)
        const grad = ctx.createRadialGradient(0, -10, 2, 0, -10 - coneDist, coneDist);
        grad.addColorStop(0, 'rgba(0, 240, 255, 0.35)');
        grad.addColorStop(1, 'rgba(0, 240, 255, 0.0)');
        ctx.fillStyle = grad;
        ctx.beginPath();
        ctx.moveTo(0, -8);
        ctx.arc(0, -8, coneDist, -Math.PI / 2 - coneAngle / 2, -Math.PI / 2 + coneAngle / 2);
        ctx.closePath();
        ctx.fill();

        // Bodi ROV (Hull)
        ctx.fillStyle = '#0284c7';
        ctx.strokeStyle = '#38bdf8';
        ctx.lineWidth = 1.5;

        // Rounded hull rectangle
        ctx.beginPath();
        ctx.roundRect(-8, -12, 16, 24, 4);
        ctx.fill();
        ctx.stroke();

        // Thrusters samping
        ctx.fillStyle = '#0f172a';
        ctx.fillRect(-11, -6, 3, 12);
        ctx.fillRect(8, -6, 3, 12);

        // Arah Panah Haluan (Heading Arrow)
        ctx.fillStyle = '#f59e0b';
        ctx.beginPath();
        ctx.moveTo(0, -16);
        ctx.lineTo(4, -10);
        ctx.lineTo(-4, -10);
        ctx.closePath();
        ctx.fill();

        // Center indicator light
        ctx.fillStyle = '#10b981';
        ctx.beginPath();
        ctx.arc(0, 0, 2.5, 0, Math.PI * 2);
        ctx.fill();

        ctx.restore();

        // ROV Floating Coordinate Tag
        ctx.fillStyle = isLight ? '#0f172a' : '#f8fafc';
        ctx.font = 'bold 10px "JetBrains Mono", monospace';
        ctx.textAlign = 'left';
        ctx.fillText(
            `X:${(curX >= 0 ? '+' : '') + curX.toFixed(2)}m Y:${(curY >= 0 ? '+' : '') + curY.toFixed(2)}m`,
            rovScreen.x + 16,
            rovScreen.y - 6
        );

        ctx.fillStyle = '#38bdf8';
        ctx.font = '9px "JetBrains Mono", monospace';
        ctx.fillText(`HDG: ${curYaw.toFixed(1)}°`, rovScreen.x + 16, rovScreen.y + 6);

        // ── E. SCALE INDICATOR (POJOK KIRI BAWAH) ──
        const scaleBarMeters = 1.0;
        const scaleBarPx = scaleBarMeters * zoomScale;
        ctx.strokeStyle = labelColor;
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(16, H - 18);
        ctx.lineTo(16 + scaleBarPx, H - 18);
        ctx.moveTo(16, H - 22);
        ctx.lineTo(16, H - 14);
        ctx.moveTo(16 + scaleBarPx, H - 22);
        ctx.lineTo(16 + scaleBarPx, H - 14);
        ctx.stroke();

        ctx.fillStyle = labelColor;
        ctx.font = '9px "JetBrains Mono", monospace';
        ctx.textAlign = 'center';
        ctx.fillText(`${scaleBarMeters.toFixed(1)} m`, 16 + scaleBarPx / 2, H - 6);

        ctx.restore();
    }, [
        telemetry,
        fallbackPos,
        fallbackYaw,
        livePath,
        zoomScale,
        panOffset,
        autoCenter,
        isBackendConnected,
        theme,
    ]);

    // Hitung jarak Euclidean dari origin
    const distFromOrigin = Math.hypot(telemetry.x, telemetry.y);

    // Footer Panel dengan tombol kontrol lengkap
    const footer = (
        <div className="traj-panel-footer">
            <div className="traj-footer-left">
                {/* Tombol Kalibrasi Titik Origin */}
                <button
                    className={`action-btn btn-calibrate ${isCalibrating ? 'active' : ''}`}
                    onClick={handleCalibrateOrigin}
                    title="Jadikan posisi ROV saat ini sebagai titik (0,0) origin"
                >
                    <span className="btn-icon">🎯</span> KALIBRASI ORIGIN (0,0)
                </button>

                {/* Tombol Reset Origin ke (0,0) default */}
                <button
                    className="action-btn btn-reset-origin"
                    onClick={handleResetOrigin}
                    title="Reset origin offset kembali ke 0.0"
                >
                    ↺ Reset Origin
                </button>
            </div>

            <div className="traj-footer-right">
                {/* Switch Sumber Data REAL / DUMMY */}
                <button
                    className={`action-btn btn-source-toggle ${telemetry.source === 'real' ? 'real-mode' : 'dummy-mode'}`}
                    onClick={toggleSource}
                    title="Ganti antara telemetry Pixhawk MAVLink dan Simulasi Dummy"
                >
                    {telemetry.source.toUpperCase()}
                </button>

                {/* Tombol Bersihkan Jejak */}
                <button
                    className="action-btn"
                    onClick={handleClearPath}
                    title="Hapus garis riwayat lintasan di layar"
                >
                    Clear Path
                </button>
            </div>
        </div>
    );

    return (
        <PanelWrapper
            className="traj-panel"
            title="TRAJECTORY MAP — REALTIME TOP-DOWN VIEW"
            footer={footer}
            onLayoutChange={resizeCanvas}
        >
            <div className="traj-canvas-container">
                <canvas
                    ref={canvasRef}
                    id="traj-canvas"
                    onMouseDown={handleMouseDown}
                    onMouseMove={handleMouseMove}
                    onMouseUp={handleMouseUp}
                    onMouseLeave={handleMouseUp}
                    onWheel={handleWheel}
                    style={{ cursor: isDragging ? 'grabbing' : 'grab' }}
                />

                {/* HUD Overlay Kiri Atas: Nilai Telemetri Realtime */}
                <div className="traj-hud-overlay">
                    <div className="traj-hud-item">
                        <span className="hud-label">POS X:</span>
                        <span className="hud-val">{(telemetry.x >= 0 ? '+' : '') + telemetry.x.toFixed(3)} m</span>
                    </div>
                    <div className="traj-hud-item">
                        <span className="hud-label">POS Y:</span>
                        <span className="hud-val">{(telemetry.y >= 0 ? '+' : '') + telemetry.y.toFixed(3)} m</span>
                    </div>
                    <div className="traj-hud-item">
                        <span className="hud-label">DEPTH:</span>
                        <span className="hud-val">{telemetry.z.toFixed(2)} m</span>
                    </div>
                    <div className="traj-hud-item">
                        <span className="hud-label">DIST:</span>
                        <span className="hud-val hud-dist">{distFromOrigin.toFixed(2)} m</span>
                    </div>
                    <div className="traj-hud-item">
                        <span className="hud-label">HEADING:</span>
                        <span className="hud-val hud-hdg">{telemetry.yaw.toFixed(1)}°</span>
                    </div>
                </div>

                {/* HUD Kanan Atas: Status Koneksi MAVLink & Port 8007 */}
                <div className="traj-status-overlay">
                    <div className={`status-pill ${isBackendConnected ? 'connected' : 'disconnected'}`}>
                        {isBackendConnected ? '● API 8007 OK' : '○ API OFFLINE'}
                    </div>
                    <div className={`status-pill ${telemetry.mavlink_connected ? 'mavlink-ok' : 'mavlink-off'}`}>
                        {telemetry.mavlink_connected ? '● MAVLink OK' : '○ No MAVLink'}
                    </div>
                </div>

                {/* Map Control Toolbar Kanan Bawah */}
                <div className="traj-map-controls">
                    <button
                        className={`map-ctrl-btn ${autoCenter ? 'active' : ''}`}
                        onClick={() => {
                            setAutoCenter(!autoCenter);
                            if (!autoCenter) setPanOffset({ x: 0, y: 0 });
                        }}
                        title={autoCenter ? 'Auto-Center Aktif' : 'Pusatkan ke ROV'}
                    >
                        🎯
                    </button>
                    <button
                        className="map-ctrl-btn"
                        onClick={() => setZoomScale((prev) => Math.min(180, prev * 1.25))}
                        title="Zoom In"
                    >
                        +
                    </button>
                    <button
                        className="map-ctrl-btn"
                        onClick={() => setZoomScale((prev) => Math.max(15, prev * 0.8))}
                        title="Zoom Out"
                    >
                        −
                    </button>
                    <button
                        className="map-ctrl-btn"
                        onClick={() => {
                            setZoomScale(45);
                            setPanOffset({ x: 0, y: 0 });
                            setAutoCenter(true);
                        }}
                        title="Reset View"
                    >
                        ⛶
                    </button>
                </div>

                {/* Toast Pop-up Notification */}
                {toastMessage && (
                    <div className="traj-toast">
                        {toastMessage}
                    </div>
                )}
            </div>
        </PanelWrapper>
    );
};
