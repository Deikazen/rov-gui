import React, { useState, useEffect } from "react";
import { PanelWrapper } from "./PanelWrapper";
import type { DepthTelemetryData } from "../hooks/useDepth";

interface TelemetryData {
  source: "real" | "dummy";
  depth: number;
  depth_cm: number;
  rate: number;
  mavlink_connected: boolean;
}

interface AltitudePanelProps {
  altitude?: number;
  altPrev?: number;
  depthTelemetry?: DepthTelemetryData;
  onToggleSource?: (source: "real" | "dummy") => void;
  onTare?: () => void;
}

export const AltitudePanel: React.FC<AltitudePanelProps> = ({
  altitude: fallbackAltitude = 0,
  depthTelemetry,
  onToggleSource,
  onTare,
}) => {
  const [internalTelemetry, setInternalTelemetry] = useState<TelemetryData>({
    source: "real",
    depth: fallbackAltitude,
    depth_cm: fallbackAltitude * 100,
    rate: 0,
    mavlink_connected: false,
  });

  // Jika depthTelemetry tidak dioper dari parent, fetch sendiri dari Flask
  useEffect(() => {
    if (depthTelemetry) return;

    const interval = setInterval(async () => {
      try {
        const response = await fetch("http://127.0.0.1:5001/api/telemetry");
        if (!response.ok) return;

        const data: TelemetryData = await response.json();
        setInternalTelemetry(data);
      } catch (error) {
        console.error("Gagal mengambil data telemetri:", error);
      }
    }, 50);

    return () => clearInterval(interval);
  }, [depthTelemetry]);

  // Fungsi untuk mengganti sumber data (Real / Dummy)
  const handleToggleSource = async (newSource: "real" | "dummy") => {
    if (onToggleSource) {
      onToggleSource(newSource);
      return;
    }
    setInternalTelemetry((prev) => ({ ...prev, source: newSource }));
    try {
      await fetch("http://127.0.0.1:5001/api/source", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ source: newSource }),
      });
    } catch (error) {
      console.error("Gagal mengubah source:", error);
    }
  };

  const telemetry = depthTelemetry
    ? {
        source: depthTelemetry.source,
        depth: depthTelemetry.backendOnline ? depthTelemetry.depth : fallbackAltitude,
        depth_cm: depthTelemetry.backendOnline ? depthTelemetry.depth_cm : fallbackAltitude * 100,
        rate: depthTelemetry.rate,
        mavlink_connected: depthTelemetry.mavlink_connected,
      }
    : internalTelemetry;

  const currentAltitude = telemetry.depth;
  const pct = Math.min(1, Math.max(0, currentAltitude / 5.0));
  const isDanger = currentAltitude < 0.3;
  const isWarning = currentAltitude < 1.5;
  const colorVar = isDanger
    ? "var(--red)"
    : isWarning
      ? "var(--amber)"
      : "var(--green)";

  // Format nilai rate langsung dari backend
  const formattedRate =
    (telemetry.rate >= 0 ? "+" : "") + telemetry.rate.toFixed(2);

  return (
    <PanelWrapper className="alt-panel" title="ALTITUDE — DEPTH SENSOR">
      <div className="alt-gauge-wrap">
        <div className="alt-gauge-track">
          <div
            className="alt-gauge-fill"
            style={{ height: `${pct * 100}%`, background: colorVar }}
          />
        </div>
        <div
          style={{
            fontSize: "9px",
            color: "var(--text-muted)",
            fontFamily: "JetBrains Mono",
          }}
        >
          0.0m
        </div>
      </div>

      <div className="alt-gauge-labels">
        <span>5.0</span>
        <span>4.0</span>
        <span>3.0</span>
        <span>2.0</span>
        <span>1.0</span>
        <span>0.0</span>
      </div>

      <div className="alt-readout">
        <div className="alt-label">ALTITUDE</div>
        <div className="alt-value" style={{ color: colorVar }}>
          {currentAltitude.toFixed(2)}
        </div>
        <div className="alt-unit">METERS</div>

        <div className="alt-danger" style={{ opacity: isDanger ? 1 : 0 }}>
          ⚠ DANGER ZONE
        </div>

        <div
          style={{
            marginTop: "4px",
            fontSize: "10px",
            color: "var(--text-muted)",
          }}
        >
          MIN <span style={{ color: "var(--text-main)" }}>0.20</span> | MAX{" "}
          <span style={{ color: "var(--text-main)" }}>3.50</span>
        </div>

        <div
          style={{
            fontSize: "10px",
            color: "var(--text-muted)",
            marginTop: "2px",
          }}
        >
          RATE{" "}
          <span style={{ color: "var(--amber)", fontFamily: "JetBrains Mono" }}>
            {formattedRate}
          </span>{" "}
          m/s
        </div>

        {/* Status Mode & MAVLink */}
        <div
          style={{
            marginTop: "10px",
            paddingTop: "6px",
            borderTop: "1px solid #333",
            fontSize: "10px",
            display: "flex",
            gap: "6px",
            alignItems: "center",
          }}
        >
          {/* Segmented Mode Selector: REAL vs DUMMY */}
          <div
            style={{
              display: "inline-flex",
              borderRadius: "4px",
              overflow: "hidden",
              border: "1px solid #444",
              background: "#1e1e1e",
            }}
          >
            <button
              type="button"
              onClick={() => handleToggleSource("real")}
              title="Aktifkan pembacaan data nyata dari sensor Pixhawk"
              style={{
                padding: "2px 7px",
                fontSize: "9px",
                cursor: "pointer",
                background: telemetry.source === "real" ? "#0284c7" : "transparent",
                color: telemetry.source === "real" ? "#ffffff" : "var(--text-muted)",
                border: "none",
                fontWeight: telemetry.source === "real" ? "bold" : "normal",
                transition: "all 0.15s ease",
              }}
            >
              REAL
            </button>
            <button
              type="button"
              onClick={() => handleToggleSource("dummy")}
              title="Aktifkan simulasi dummy"
              style={{
                padding: "2px 7px",
                fontSize: "9px",
                cursor: "pointer",
                background: telemetry.source === "dummy" ? "#4b5563" : "transparent",
                color: telemetry.source === "dummy" ? "#ffffff" : "var(--text-muted)",
                border: "none",
                borderLeft: "1px solid #444",
                fontWeight: telemetry.source === "dummy" ? "bold" : "normal",
                transition: "all 0.15s ease",
              }}
            >
              DUMMY
            </button>
          </div>

          {/* Tombol TARE: Selalu tampil saat mode REAL */}
          {telemetry.source === "real" && (
            <button
              type="button"
              onClick={async () => {
                if (onTare) {
                  onTare();
                  return;
                }
                try {
                  const res = await fetch("http://127.0.0.1:5001/api/calibrate", { method: "POST" });
                  if (!res.ok) {
                    throw new Error(`HTTP ${res.status}`);
                  }
                } catch (e) {
                  console.error("Gagal tare sensor:", e);
                }
              }}
              title="Tare / Nolkan pembacaan sensor kedalaman di permukaan saat ini"
              style={{
                padding: "2px 7px",
                fontSize: "9px",
                cursor: "pointer",
                background: "#059669",
                color: "#fff",
                border: "none",
                borderRadius: "3px",
                fontWeight: "bold",
              }}
            >
              TARE
            </button>
          )}

          <span
            style={{
              color: telemetry.mavlink_connected
                ? "var(--green)"
                : "var(--red)",
            }}
          >
            {telemetry.mavlink_connected ? "● MAVLink OK" : "○ No MAVLink"}
          </span>
        </div>
      </div>
    </PanelWrapper>
  );
};
