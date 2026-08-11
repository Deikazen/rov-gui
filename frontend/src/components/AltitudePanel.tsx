import React, { useState, useEffect } from "react";
import { PanelWrapper } from "./PanelWrapper";

interface TelemetryData {
  source: "real" | "dummy";
  depth: number;
  depth_cm: number;
  rate: number;
  mavlink_connected: boolean;
}

export const AltitudePanel: React.FC = () => {
  const [telemetry, setTelemetry] = useState<TelemetryData>({
    source: "dummy",
    depth: 0,
    depth_cm: 0,
    rate: 0,
    mavlink_connected: false,
  });

  // Fetch data dari Flask setiap 100ms
  useEffect(() => {
    const interval = setInterval(async () => {
      try {
        const response = await fetch("http://localhost:5001/api/telemetry");
        if (!response.ok) return;

        const data: TelemetryData = await response.json();
        setTelemetry(data);
      } catch (error) {
        console.error("Gagal mengambil data telemetri:", error);
      }
    }, 100);

    return () => clearInterval(interval);
  }, []);

  // Fungsi untuk mengganti sumber data (Real / Dummy)
  const toggleSource = async (newSource: "real" | "dummy") => {
    try {
      await fetch("http://localhost:5001/api/source", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ source: newSource }),
      });
    } catch (error) {
      console.error("Gagal mengubah source:", error);
    }
  };

  const altitude = telemetry.depth;
  const pct = Math.min(1, Math.max(0, altitude / 5.0));
  const isDanger = altitude < 0.3;
  const isWarning = altitude < 1.5;
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
          {altitude.toFixed(2)}
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
          <button
            onClick={() =>
              toggleSource(telemetry.source === "real" ? "dummy" : "real")
            }
            style={{
              padding: "2px 6px",
              fontSize: "9px",
              cursor: "pointer",
              background: telemetry.source === "real" ? "#0284c7" : "#4b5563",
              color: "#fff",
              border: "none",
              borderRadius: "3px",
            }}
          >
            {telemetry.source.toUpperCase()}
          </button>

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
