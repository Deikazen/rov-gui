import { useState, useEffect, useCallback, useRef } from "react";

export interface DepthTelemetryData {
  source: "real" | "dummy";
  depth: number;
  depth_cm: number;
  rate: number;
  mavlink_connected: boolean;
  depthOk: boolean;
  backendOnline: boolean;
  surface_pressure_hpa?: number | null;
  raw_pressure_hpa?: number | null;
}

const WS_DEPTH_URL = "ws://127.0.0.1:8081";
const HTTP_DEPTH_URL = "http://127.0.0.1:5001/api/telemetry";
const HTTP_SOURCE_URL = "http://127.0.0.1:5001/api/source";
const HTTP_TARE_URL = "http://127.0.0.1:5001/api/tare";

export function useDepth(fallbackSimDepth: number = 0) {
  const fallbackRef = useRef(fallbackSimDepth);
  fallbackRef.current = fallbackSimDepth;

  const isTogglingRef = useRef(false);
  const consecutiveFailuresRef = useRef(0);
  const wsRef = useRef<WebSocket | null>(null);
  const isWsConnectedRef = useRef(false);

  const [telemetry, setTelemetry] = useState<DepthTelemetryData>({
    source: "real",
    depth: 0,
    depth_cm: 0,
    rate: 0,
    mavlink_connected: false,
    depthOk: true,
    backendOnline: false,
    surface_pressure_hpa: null,
    raw_pressure_hpa: null,
  });

  const applyTelemetryData = useCallback((data: any) => {
    consecutiveFailuresRef.current = 0;
    const isReal = data.source === "real";
    const isOk = isReal ? Boolean(data.mavlink_connected) : true;

    setTelemetry((prev) => ({
      // Jangan timpa mode jika user baru saja menekan tombol toggle
      source: isTogglingRef.current ? prev.source : (data.source || "real"),
      depth: typeof data.depth === "number" ? data.depth : prev.depth,
      depth_cm: typeof data.depth_cm === "number" ? data.depth_cm : prev.depth_cm,
      rate: typeof data.rate === "number" ? data.rate : 0,
      mavlink_connected: Boolean(data.mavlink_connected),
      depthOk: isOk,
      backendOnline: true,
      surface_pressure_hpa: data.surface_pressure_hpa ?? prev.surface_pressure_hpa,
      raw_pressure_hpa: data.raw_pressure_hpa ?? prev.raw_pressure_hpa,
    }));
  }, []);

  // 1. WebSocket Real-time Push Stream (Port 8081) - Latensi < 5ms
  useEffect(() => {
    let isMounted = true;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;

    const connectWebSocket = () => {
      if (!isMounted) return;
      try {
        const ws = new WebSocket(WS_DEPTH_URL);
        wsRef.current = ws;

        ws.onopen = () => {
          if (!isMounted) return;
          console.log("[WS DEPTH] Terhubung ke ws://127.0.0.1:8081 (Real-time telemetry stream active)");
          isWsConnectedRef.current = true;
        };

        ws.onmessage = (event) => {
          if (!isMounted) return;
          try {
            const data = JSON.parse(event.data);
            applyTelemetryData(data);
          } catch (err) {
            console.error("[WS DEPTH] Gagal parse JSON:", err);
          }
        };

        ws.onclose = () => {
          if (!isMounted) return;
          isWsConnectedRef.current = false;
          reconnectTimer = setTimeout(connectWebSocket, 2000);
        };

        ws.onerror = () => {
          if (!isMounted) return;
          isWsConnectedRef.current = false;
          try {
            ws.close();
          } catch {}
        };
      } catch {
        if (isMounted) {
          isWsConnectedRef.current = false;
          reconnectTimer = setTimeout(connectWebSocket, 2000);
        }
      }
    };

    connectWebSocket();

    return () => {
      isMounted = false;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      if (wsRef.current) {
        try {
          wsRef.current.close();
        } catch {}
      }
    };
  }, [applyTelemetryData]);

  // 2. HTTP Polling Fallback - Aktif hanya saat WebSocket tidak terhubung
  useEffect(() => {
    let isMounted = true;
    let timerId: ReturnType<typeof setTimeout> | null = null;
    let isFetching = false;

    const fetchTelemetry = async () => {
      if (!isMounted) return;

      // Jika WebSocket sudah aktif melayani data secara real-time, tunda polling HTTP
      if (isWsConnectedRef.current) {
        timerId = setTimeout(fetchTelemetry, 300);
        return;
      }

      if (isFetching) return;
      isFetching = true;
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 1200);

      try {
        const response = await fetch(HTTP_DEPTH_URL, {
          signal: controller.signal,
        });
        clearTimeout(timeoutId);
        if (!response.ok) {
          throw new Error(`HTTP error ${response.status}`);
        }

        const data = await response.json();
        if (isMounted) {
          applyTelemetryData(data);
        }
      } catch {
        clearTimeout(timeoutId);
        if (!isMounted) return;

        consecutiveFailuresRef.current++;

        // HANYA fallback ke data simulasi jika backend BENAR-BENAR mati lama (> 15 kali berturut-turut)
        if (consecutiveFailuresRef.current > 15) {
          setTelemetry((prev) => ({
            ...prev,
            depth: fallbackRef.current,
            depth_cm: fallbackRef.current * 100,
            backendOnline: false,
            depthOk: true,
          }));
        }
      } finally {
        isFetching = false;
        if (isMounted) {
          timerId = setTimeout(fetchTelemetry, 50);
        }
      }
    };

    timerId = setTimeout(fetchTelemetry, 50);

    return () => {
      isMounted = false;
      if (timerId) clearTimeout(timerId);
    };
  }, [applyTelemetryData]);

  // 3. Toggle Source: Kirim via WebSocket (instan) & HTTP (backup)
  const toggleSource = useCallback(async (newSource: "real" | "dummy") => {
    isTogglingRef.current = true;

    // Optimistic UI update agar tombol langsung berganti tanpa kedip
    setTelemetry((prev) => ({
      ...prev,
      source: newSource,
      depthOk: newSource === "real" ? prev.mavlink_connected : true,
    }));

    // Kirim via WS jika aktif
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      try {
        wsRef.current.send(JSON.stringify({ action: "set_source", source: newSource }));
      } catch {}
    }

    // Backup HTTP
    try {
      await fetch(HTTP_SOURCE_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ source: newSource }),
      });
    } catch (error) {
      console.error("Gagal mengubah source depth via HTTP:", error);
    } finally {
      setTimeout(() => {
        isTogglingRef.current = false;
      }, 400);
    }
  }, []);

  // 4. Tare Sensor: Nolkan pembacaan di permukaan seketika
  const tare = useCallback(async () => {
    setTelemetry((prev) => ({
      ...prev,
      depth: 0,
      depth_cm: 0,
    }));

    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      try {
        wsRef.current.send(JSON.stringify({ action: "tare" }));
      } catch {}
    }

    try {
      await fetch(HTTP_TARE_URL, { method: "POST" });
    } catch (err) {
      console.error("Gagal tare sensor via HTTP:", err);
    }
  }, []);

  return {
    ...telemetry,
    toggleSource,
    tare,
  };
}
