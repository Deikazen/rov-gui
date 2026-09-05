import { useState, useEffect, useCallback, useRef } from "react";

export interface DepthTelemetryData {
  source: "real" | "dummy";
  depth: number;
  depth_cm: number;
  rate: number;
  mavlink_connected: boolean;
  depthOk: boolean;
  backendOnline: boolean;
}

export function useDepth(fallbackSimDepth: number = 0) {
  const fallbackRef = useRef(fallbackSimDepth);
  fallbackRef.current = fallbackSimDepth;

  const isTogglingRef = useRef(false);
  const consecutiveFailuresRef = useRef(0);
  const fetchTelemetryRef = useRef<() => Promise<void>>(null);

  const [telemetry, setTelemetry] = useState<DepthTelemetryData>({
    source: "real",
    depth: 0,
    depth_cm: 0,
    rate: 0,
    mavlink_connected: false,
    depthOk: true,
    backendOnline: false,
  });

  useEffect(() => {
    let isMounted = true;
    let isFetching = false;
    let timerId: ReturnType<typeof setTimeout> | null = null;

    const fetchTelemetry = async () => {
      if (isFetching || !isMounted) return;
      isFetching = true;
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 1200);

      try {
        const response = await fetch("http://127.0.0.1:5001/api/telemetry", {
          signal: controller.signal,
        });
        clearTimeout(timeoutId);
        if (!response.ok) {
          throw new Error(`HTTP error ${response.status}`);
        }

        const data = await response.json();
        if (!isMounted) return;

        // Reset kegagalan koneksi jika respons sukses
        consecutiveFailuresRef.current = 0;

        const isReal = data.source === "real";
        const isOk = isReal ? Boolean(data.mavlink_connected) : true;

        setTelemetry((prev) => ({
          // Jangan timpa mode jika user baru saja menekan tombol toggle (cegah race condition)
          source: isTogglingRef.current ? prev.source : (data.source || "real"),
          depth: typeof data.depth === "number" ? data.depth : prev.depth,
          depth_cm: typeof data.depth_cm === "number" ? data.depth_cm : prev.depth_cm,
          rate: typeof data.rate === "number" ? data.rate : 0,
          mavlink_connected: Boolean(data.mavlink_connected),
          depthOk: isOk,
          backendOnline: true,
        }));
      } catch {
        clearTimeout(timeoutId);
        if (!isMounted) return;

        consecutiveFailuresRef.current++;

        // HANYA fallback ke data simulasi jika backend BENAR-BENAR mati lama (> 15 kali berturut-turut / ~1.5 detik)
        // Jika hanya glitch sesaat / frame drop, JANGAN LOMPAT ke data simulasi! Pertahankan nilai terakhir!
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
          // Chained timeout agar request tidak menumpuk / berhimpitan
          timerId = setTimeout(fetchTelemetry, 50);
        }
      }
    };

    fetchTelemetryRef.current = fetchTelemetry;
    fetchTelemetry();

    return () => {
      isMounted = false;
      if (timerId) clearTimeout(timerId);
    };
  }, []);

  const toggleSource = useCallback(async (newSource: "real" | "dummy") => {
    isTogglingRef.current = true;

    // Optimistic UI update agar tombol langsung berubah seketika saat diklik
    setTelemetry((prev) => ({
      ...prev,
      source: newSource,
      depthOk: newSource === "real" ? prev.mavlink_connected : true,
    }));

    try {
      const res = await fetch("http://127.0.0.1:5001/api/source", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ source: newSource }),
      });
      if (res.ok && fetchTelemetryRef.current) {
        // Ambil data terbaru segera setelah sumber diubah di backend
        fetchTelemetryRef.current();
      }
    } catch (error) {
      console.error("Gagal mengubah source depth:", error);
    } finally {
      // Buka kunci proteksi setelah 400ms agar data GET tidak menimpa seleksi user
      setTimeout(() => {
        isTogglingRef.current = false;
      }, 400);
    }
  }, []);

  return {
    ...telemetry,
    toggleSource,
  };
}
