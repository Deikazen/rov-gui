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

  const [telemetry, setTelemetry] = useState<DepthTelemetryData>({
    source: "dummy",
    depth: fallbackSimDepth,
    depth_cm: fallbackSimDepth * 100,
    rate: 0,
    mavlink_connected: false,
    depthOk: true,
    backendOnline: false,
  });

  useEffect(() => {
    let isMounted = true;
    let isFetching = false;

    const fetchTelemetry = async () => {
      if (isFetching) return;
      isFetching = true;

      try {
        const response = await fetch("http://localhost:5001/api/telemetry");
        if (!response.ok) {
          throw new Error(`HTTP error ${response.status}`);
        }

        const data = await response.json();
        if (!isMounted) return;

        const isReal = data.source === "real";
        const isOk = isReal ? Boolean(data.mavlink_connected) : true;

        setTelemetry({
          source: data.source || "dummy",
          depth: typeof data.depth === "number" ? data.depth : 0,
          depth_cm: typeof data.depth_cm === "number" ? data.depth_cm : 0,
          rate: typeof data.rate === "number" ? data.rate : 0,
          mavlink_connected: Boolean(data.mavlink_connected),
          depthOk: isOk,
          backendOnline: true,
        });
      } catch {
        if (!isMounted) return;
        // Backend offline: fallback ke simulasi
        setTelemetry((prev) => ({
          ...prev,
          depth: fallbackRef.current,
          depth_cm: fallbackRef.current * 100,
          backendOnline: false,
          depthOk: true, // fallback simulasi tetap aktif
        }));
      } finally {
        isFetching = false;
      }
    };

    fetchTelemetry();
    const interval = setInterval(fetchTelemetry, 100);

    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, []);

  const toggleSource = useCallback(async (newSource: "real" | "dummy") => {
    // Optimistic UI update agar tombol langsung berubah seketika saat diklik
    setTelemetry((prev) => ({
      ...prev,
      source: newSource,
      depthOk: newSource === "real" ? prev.mavlink_connected : true,
    }));

    try {
      await fetch("http://localhost:5001/api/source", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ source: newSource }),
      });
    } catch (error) {
      console.error("Gagal mengubah source depth:", error);
    }
  }, []);

  return {
    ...telemetry,
    toggleSource,
  };
}
