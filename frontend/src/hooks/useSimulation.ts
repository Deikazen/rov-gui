import { useState, useEffect, useRef, useCallback } from 'react';
import type { LogSample, CameraState, ImuData, Point2D } from '../types/telemetry';

const QR_CYCLE = ['A', 'B', 'C', 'D', 'INVALID'];
const TRAJ_PATH: Point2D[] = [
    { x: 0.08, y: 0.85 }, { x: 0.15, y: 0.75 }, { x: 0.25, y: 0.60 },
    { x: 0.30, y: 0.45 }, { x: 0.40, y: 0.35 }, { x: 0.50, y: 0.28 },
    { x: 0.60, y: 0.30 }, { x: 0.68, y: 0.42 }, { x: 0.72, y: 0.55 },
    { x: 0.78, y: 0.65 }, { x: 0.85, y: 0.55 }, { x: 0.90, y: 0.40 },
    { x: 0.88, y: 0.20 }, { x: 0.92, y: 0.12 }
];

export function useSimulation() {
    // Clock & Date
    const [timeString, setTimeString] = useState('00:00:00');
    const [dateString, setDateString] = useState('LOADING...');
    const [camTimestamp, setCamTimestamp] = useState('00:00:00.000');

    // Controls & Modes
    const [mode, setMode] = useState<'MANUAL' | 'AUTONOMOUS'>('MANUAL');
    const [emergencyActive, setEmergencyActive] = useState(false);
    const [theme, setTheme] = useState<'dark' | 'light'>('dark');
    const [connected, setConnected] = useState(true);
    const [imuOk, setImuOk] = useState(true);
    const [logging, setLogging] = useState(false);
    const [logData, setLogData] = useState<LogSample[]>([]);

    // Telemetry
    const [altitude, setAltitude] = useState(2.45);
    const [altPrev, setAltPrev] = useState(2.45);
    const [qrIdx, setQrIdx] = useState(0);
    const [qrScanCount, setQrScanCount] = useState(47);
    const [qrConf, setQrConf] = useState('98.7%');

    // IMU
    const [imu, setImu] = useState<ImuData>({ roll: 0, pitch: 0, yaw: 0 });

    // Trajectory
    const [rovPos, setRovPos] = useState<Point2D>({ x: 0.08, y: 0.85 });
    const [recordedPath, setRecordedPath] = useState<Point2D[]>([]);
    const [isReplaying, setIsReplaying] = useState(false);

    // Cameras
    const [cams, setCams] = useState<Record<number, CameraState>>({
        1: { duration: 20, time: 0, playing: true },
        2: { duration: 20, time: 7, playing: true }
    });

    // Refs for simulation calculation
    const simTimeRef = useRef(0);
    const pathProgressRef = useRef(0);
    const lastTimeRef = useRef(0);
    const logTimerRef = useRef(0);
    const qrTimerRef = useRef(0);
    const connTimerRef = useRef(0);
    const nextConnFlickerRef = useRef(30000);
    const alarmActiveRef = useRef(false);
    const audioCtxRef = useRef<AudioContext | null>(null);
    const isWsConnectedRef = useRef(false);
    const hasTrajectoryYawRef = useRef(false);

    // Audio Alert function
    const playBeep = useCallback(() => {
        try {
            if (!audioCtxRef.current) {
                const AudioCtx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
                audioCtxRef.current = new AudioCtx();
            }
            const ctx = audioCtxRef.current;
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();
            osc.connect(gain);
            gain.connect(ctx.destination);
            osc.type = 'square';
            osc.frequency.setValueAtTime(880, ctx.currentTime);
            osc.frequency.setValueAtTime(440, ctx.currentTime + 0.1);
            gain.gain.setValueAtTime(0.1, ctx.currentTime);
            gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.3);
            osc.start(ctx.currentTime);
            osc.stop(ctx.currentTime + 0.3);
        } catch {
            // Audio policy ignore
        }
    }, []);

    // Main Clock Timer
    useEffect(() => {
        const updateClock = () => {
            const now = new Date();
            const days = ['SUN', 'MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT'];
            const months = ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC'];
            const h = String(now.getHours()).padStart(2, '0');
            const m = String(now.getMinutes()).padStart(2, '0');
            const s = String(now.getSeconds()).padStart(2, '0');
            const ms = String(now.getMilliseconds()).padStart(3, '0');

            setTimeString(`${h}:${m}:${s}`);
            setDateString(`${days[now.getDay()]}  ${String(now.getDate()).padStart(2, '0')} ${months[now.getMonth()]} ${now.getFullYear()}`);
            setCamTimestamp(`${h}:${m}:${s}.${ms}`);
        };

        updateClock();
        const interval = setInterval(updateClock, 1000);
        return () => clearInterval(interval);
    }, []);

    // Realtime Telemetry WebSocket connection to backend (model_3d.py)
    useEffect(() => {
        let isComponentMounted = true;
        let ws: WebSocket | null = null;
        let reconnectTimer: ReturnType<typeof setTimeout> | null = null;

        const connectWS = () => {
            try {
                ws = new WebSocket('ws://127.0.0.1:8082');

                ws.onopen = () => {
                    if (!isComponentMounted) return;
                    console.log('[WS TELEMETRY] Terhubung ke server model_3d.py (ws://127.0.0.1:8082)');
                    isWsConnectedRef.current = true;
                    setConnected(true);
                    setImuOk(true);
                };

                ws.onmessage = (event) => {
                    if (!isComponentMounted) return;
                    try {
                        const data = JSON.parse(event.data);
                        if (data.type === 'telemetry') {
                            setImu({
                                roll: Number(data.roll) || 0,
                                pitch: Number(data.pitch) || 0,
                                yaw: Number(data.yaw) || 0,
                            });
                            setImuOk(true);
                        } else if (data.type === 'status') {
                            const mavOnline = Boolean(data.mavlink_online);
                            setConnected(mavOnline);
                            setImuOk(mavOnline);
                        }
                    } catch (err) {
                        console.error('[WS TELEMETRY] Error parsing message:', err);
                    }
                };

                ws.onclose = () => {
                    if (!isComponentMounted) return;
                    isWsConnectedRef.current = false;
                    reconnectTimer = setTimeout(connectWS, 3000);
                };

                ws.onerror = () => {
                    if (!isComponentMounted) return;
                    isWsConnectedRef.current = false;
                    ws?.close();
                };
            } catch {
                if (isComponentMounted) {
                    reconnectTimer = setTimeout(connectWS, 3000);
                }
            }
        };

        connectWS();

        // Fallback sinkronisasi Yaw dari backend port 8007 jika WS 8082 offline
        let isPollingYaw = false;
        const pollTrajectoryYaw = setInterval(async () => {
            if (isWsConnectedRef.current || !isComponentMounted || isPollingYaw) return;
            isPollingYaw = true;
            try {
                const controller = new AbortController();
                const timeoutId = setTimeout(() => controller.abort(), 800);
                const res = await fetch('http://127.0.0.1:8007/api/trajectory', { signal: controller.signal });
                clearTimeout(timeoutId);
                if (res.ok) {
                    const data = await res.json();
                    if (data.yaw !== undefined && isComponentMounted) {
                        hasTrajectoryYawRef.current = true;
                        setImu(prev => ({
                            ...prev,
                            yaw: Number(data.yaw) || 0
                        }));
                        setImuOk(Boolean(data.mavlink_connected));
                        setConnected(Boolean(data.mavlink_connected));
                    }
                }
            } catch {
                hasTrajectoryYawRef.current = false;
            } finally {
                isPollingYaw = false;
            }
        }, 150);

        return () => {
            isComponentMounted = false;
            clearInterval(pollTrajectoryYaw);
            if (reconnectTimer) clearTimeout(reconnectTimer);
            if (ws) {
                ws.onclose = null;
                ws.close();
            }
        };
    }, []);

    // RequestAnimationFrame simulation loop
    useEffect(() => {
        let animId: number;

        const loop = (now: number) => {
            const dt = now - lastTimeRef.current;
            lastTimeRef.current = now;
            simTimeRef.current += dt;

            // 1. Altitude calculation
            const currentAlt = 0.2 + (3.3 / 2) * (1 + Math.sin((simTimeRef.current / 10000) * Math.PI * 2));
            setAltitude(prev => {
                setAltPrev(prev);
                return currentAlt;
            });

            if (currentAlt < 0.3 && !alarmActiveRef.current) {
                alarmActiveRef.current = true;
                playBeep();
                setTimeout(() => { alarmActiveRef.current = false; }, 1500);
            }

            // 2. QR calculation
            qrTimerRef.current += dt;
            if (qrTimerRef.current >= 5000) {
                qrTimerRef.current = 0;
                setQrIdx(prev => {
                    const next = (prev + 1) % QR_CYCLE.length;
                    const isValid = QR_CYCLE[next] !== 'INVALID';
                    setQrConf(isValid ? (95 + Math.random() * 4).toFixed(1) + '%' : '--.--%');
                    return next;
                });
                setQrScanCount(prev => prev + 1);
            }

            // 3. Connection flicker simulation (only if WS is not actively managing connection)
            if (!isWsConnectedRef.current) {
                connTimerRef.current += dt;
                if (connTimerRef.current >= nextConnFlickerRef.current) {
                    connTimerRef.current = 0;
                    nextConnFlickerRef.current = 28000 + Math.random() * 4000;
                    setConnected(false);
                    setTimeout(() => setConnected(true), 2000);
                }
            }

            // 4. ROV Position calculation
            if (!isReplaying) {
                pathProgressRef.current = (pathProgressRef.current + (dt / 1000) * 0.08) % (TRAJ_PATH.length - 1);
                const idx = Math.floor(pathProgressRef.current);
                const t = pathProgressRef.current - idx;
                const a = TRAJ_PATH[Math.min(idx, TRAJ_PATH.length - 1)];
                const b = TRAJ_PATH[Math.min(idx + 1, TRAJ_PATH.length - 1)];
                const rx = a.x + (b.x - a.x) * t;
                const ry = a.y + (b.y - a.y) * t;
                setRovPos({ x: rx, y: ry });

                setRecordedPath(prev => {
                    const last = prev[prev.length - 1];
                    if (!last || Math.abs(rx - last.x) > 0.005 || Math.abs(ry - last.y) > 0.005) {
                        const updated = [...prev, { x: rx, y: ry }];
                        return updated.length > 500 ? updated.slice(1) : updated;
                    }
                    return prev;
                });
            }

            // 5. IMU calculation (Only fallback to simulation if WebSocket backend is offline)
            if (!isWsConnectedRef.current) {
                const rollTarget = Math.sin(simTimeRef.current / 1500) * 4;
                const pitchTarget = Math.cos(simTimeRef.current / 1700) * 3;

                setImu(prev => {
                    const newRoll = prev.roll + (rollTarget - prev.roll) * 0.05;
                    const newPitch = prev.pitch + (pitchTarget - prev.pitch) * 0.05;
                    if (hasTrajectoryYawRef.current) {
                        return { ...prev, roll: newRoll, pitch: newPitch };
                    }
                    const yawTarget = (Math.sin(simTimeRef.current / 4000) * 45 + 180) % 360;
                    return {
                        roll: newRoll,
                        pitch: newPitch,
                        yaw: (prev.yaw + ((yawTarget - prev.yaw + 540) % 360 - 180) * 0.02 + 360) % 360,
                    };
                });
            }

            // 6. Camera replays
            setCams(prev => ({
                1: {
                    ...prev[1],
                    time: prev[1].playing ? (prev[1].time + dt / 1000) % prev[1].duration : prev[1].time
                },
                2: {
                    ...prev[2],
                    time: prev[2].playing ? (prev[2].time + dt / 1000) % prev[2].duration : prev[2].time
                }
            }));

            // 7. Logging interval
            if (logging) {
                logTimerRef.current += dt;
                if (logTimerRef.current >= 500) {
                    logTimerRef.current = 0;
                    setLogData(prev => [
                        ...prev,
                        {
                            timestamp: new Date().toISOString(),
                            altitude: currentAlt.toFixed(3),
                            posX: (rovPos.x * 10).toFixed(3),
                            posY: (rovPos.y * 10).toFixed(3),
                            roll: imu.roll.toFixed(2),
                            pitch: imu.pitch.toFixed(2),
                            yaw: imu.yaw.toFixed(2),
                            qrSide: QR_CYCLE[qrIdx],
                            connected: connected ? 1 : 0
                        }
                    ]);
                }
            }

            animId = requestAnimationFrame(loop);
        };

        animId = requestAnimationFrame(loop);
        return () => cancelAnimationFrame(animId);
    }, [isReplaying, logging, qrIdx, connected, rovPos.x, rovPos.y, imu.roll, imu.pitch, imu.yaw, playBeep]);

    // Action Methods
    const toggleCameraPlay = (id: number) => {
        setCams(prev => ({
            ...prev,
            [id]: { ...prev[id], playing: !prev[id].playing }
        }));
    };

    const seekCamera = (id: number, valPercent: number) => {
        setCams(prev => ({
            ...prev,
            [id]: {
                ...prev[id],
                time: (valPercent / 100) * prev[id].duration,
                playing: false
            }
        }));
    };

    const toggleMode = () => {
        setMode(prev => (prev === 'MANUAL' ? 'AUTONOMOUS' : 'MANUAL'));
    };

    const toggleEmergency = () => {
        setEmergencyActive(prev => !prev);
    };

    const toggleTheme = () => {
        setTheme(prev => (prev === 'dark' ? 'light' : 'dark'));
    };

    const toggleLogging = () => {
        setLogging(prev => {
            if (!prev) setLogData([]);
            return !prev;
        });
    };

    const replayTrajectory = () => {
        if (isReplaying || recordedPath.length < 2) return;
        setIsReplaying(true);
        const snap = [...recordedPath];
        setRecordedPath([]);
        let idx = 0;

        const interval = setInterval(() => {
            if (idx >= snap.length) {
                clearInterval(interval);
                setIsReplaying(false);
                setRecordedPath(snap);
                return;
            }
            const pt = snap[idx];
            setRovPos(pt);
            setRecordedPath(prev => [...prev, pt]);
            idx++;
        }, 30);
    };

    const clearPath = () => {
        setRecordedPath([]);
        pathProgressRef.current = 0;
    };

    return {
        timeString,
        dateString,
        camTimestamp,
        mode,
        emergencyActive,
        theme,
        connected,
        imuOk,
        logging,
        logData,
        altitude,
        altPrev,
        qrSide: QR_CYCLE[qrIdx],
        qrScanCount,
        qrConf,
        imu,
        rovPos,
        recordedPath,
        isReplaying,
        trajPath: TRAJ_PATH,
        cams,
        toggleCameraPlay,
        seekCamera,
        toggleMode,
        toggleEmergency,
        toggleTheme,
        toggleLogging,
        replayTrajectory,
        clearPath
    };
}
