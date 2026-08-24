import { useState, useEffect } from "react";
import { useSimulation } from "./hooks/useSimulation";
import { useQrDetector } from "./hooks/useQrDetector"; // <-- BARU: data QR real-time dari qr_proxy.py
import { Header } from "./components/Header";
import { CameraPanel } from "./components/CameraPanel";
import { QrPanel } from "./components/QrPanel";
import { AltitudePanel } from "./components/AltitudePanel";
import { TrajectoryPanel } from "./components/TrajectoryPanel";
// import { RovSchematic } from './components/RovSchematic';
import { RovStlSchematic } from "./components/RovStlSchematic";
import { FooterBar } from "./components/FooterBar";
import { ResultModal } from "./components/ResultModal";

// Ambil dari .env: VITE_CAM1_URL, VITE_CAM2_URL (lihat frontend/.env.example)
const CAM1_URL = import.meta.env.VITE_CAM1_URL as string | undefined;
const CAM2_URL = import.meta.env.VITE_CAM2_URL as string | undefined;

export function App() {
  const {
    timeString,
    dateString,
    camTimestamp,
    mode,
    emergencyActive,
    theme,
    connected,
    logging,
    logData,
    altitude,
    altPrev,
    // qrSide, qrScanCount, qrConf TIDAK dipakai lagi dari sini (masih dummy/simulasi).
    // Data QR panel sekarang diambil real-time dari useQrDetector() di bawah.
    imu,
    rovPos,
    recordedPath,
    isReplaying,
    trajPath,
    cams,
    toggleCameraPlay,
    seekCamera,
    toggleMode,
    toggleEmergency,
    toggleTheme,
    toggleLogging,
    replayTrajectory,
    clearPath,
  } = useSimulation();

  // Data QR real-time: connect ke qr_proxy.py (ws://.../ws/qr/status),
  // otomatis update begitu Camera 01 di Jetson mendeteksi QR code.
  const { side: qrSide, scanCount: qrScanCount, confidence: qrConf } =
    useQrDetector();

  // Modal State
  const [modalOpen, setModalOpen] = useState(false);
  const [modalTitle, setModalTitle] = useState("RESULT");
  const [screenshotUrl, setScreenshotUrl] = useState<string | undefined>();
  const [screenshotFilename, setScreenshotFilename] = useState<
    string | undefined
  >();

  // Full view panel controller init
  useEffect(() => {
    document.body.classList.toggle("light-theme", theme === "light");
    document.body.classList.toggle("emergency-active", emergencyActive);
  }, [theme, emergencyActive]);

  const handleDownloadCSV = () => {
    if (logData.length === 0) return;
    const headers =
      "timestamp,altitude_m,pos_x_m,pos_y_m,imu_roll_deg,imu_pitch_deg,imu_yaw_deg,qr_side,connected\n";
    const rows = logData
      .map(
        (r) =>
          `${r.timestamp},${r.altitude},${r.posX},${r.posY},${r.roll},${r.pitch},${r.yaw},${r.qrSide},${r.connected}`,
      )
      .join("\n");
    const blob = new Blob([headers + rows], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `rov_telemetry_${new Date().toISOString().replace(/[:.]/g, "-")}.csv`;
    a.click();
    URL.revokeObjectURL(url);

    setScreenshotUrl(undefined);
    setScreenshotFilename(undefined);
    setModalTitle("Automatic Data Log");
    setModalOpen(true);
  };

  const handleScreenshot = () => {
    const ts = new Date().toISOString().replace(/[:.]/g, "-");
    const filename = `rov_gcs_${ts}.png`;

    if (navigator.mediaDevices && navigator.mediaDevices.getDisplayMedia) {
      navigator.mediaDevices
        .getDisplayMedia({ video: true })
        .then((stream) => {
          const video = document.createElement("video");
          video.srcObject = stream;
          video.play().then(() => {
            const cvs = document.createElement("canvas");
            cvs.width = video.videoWidth;
            cvs.height = video.videoHeight;
            cvs.getContext("2d")?.drawImage(video, 0, 0);
            stream.getTracks().forEach((t) => t.stop());
            cvs.toBlob((blob) => {
              if (blob) {
                const url = URL.createObjectURL(blob);
                setScreenshotUrl(url);
                setScreenshotFilename(filename);
                setModalTitle("Screenshot Result");
                setModalOpen(true);
              }
            }, "image/png");
          });
        })
        .catch(() => {
          // User canceled screenshot prompt
        });
    } else {
      setScreenshotUrl(undefined);
      setScreenshotFilename(undefined);
      setModalTitle("Screenshot Result");
      setModalOpen(true);
    }
  };

  const handleToggleLogging = () => {
    if (logging && logData.length > 0) {
      setScreenshotUrl(undefined);
      setScreenshotFilename(undefined);
      setModalTitle("Automatic Data Log");
      setModalOpen(true);
    }
    toggleLogging();
  };

  return (
    <>
      <Header timeString={timeString} dateString={dateString} />

      <div id="main-content">
        <div className="row">
          <CameraPanel
            id={1}
            title="CAMERA 01 — FRONT VIEW"
            poolClass="pool-1"
            overlayLabel="KOLAM 1 — LIVE"
            timestamp={camTimestamp}
            cameraState={cams[1]}
            onTogglePlay={toggleCameraPlay}
            onSeek={seekCamera}
            streamUrl={CAM1_URL}
          />
          <CameraPanel
            id={2}
            title="CAMERA 02 — BOTTOM / SIDE VIEW"
            poolClass="pool-2"
            overlayLabel="KOLAM 2 — LIVE"
            timestamp={camTimestamp}
            cameraState={cams[2]}
            onTogglePlay={toggleCameraPlay}
            onSeek={seekCamera}
            streamUrl={CAM2_URL}
          />
          <QrPanel side={qrSide} scanCount={qrScanCount} confidence={qrConf} />
        </div>

        <div className="row">
          <AltitudePanel altitude={altitude} altPrev={altPrev} />
          <TrajectoryPanel
            rovPos={rovPos}
            recordedPath={recordedPath}
            trajPath={trajPath}
            imuYaw={imu.yaw}
            isReplaying={isReplaying}
            onReplay={replayTrajectory}
            onClear={clearPath}
            theme={theme}
          />
          <RovStlSchematic imu={imu} />
        </div>
      </div>

      <FooterBar
        mode={mode}
        emergencyActive={emergencyActive}
        connected={connected}
        logging={logging}
        hasLogData={logData.length > 0}
        theme={theme}
        depth={altitude}
        onToggleMode={toggleMode}
        onToggleEmergency={toggleEmergency}
        onToggleLogging={handleToggleLogging}
        onToggleTheme={toggleTheme}
        onScreenshot={handleScreenshot}
        onDownloadCSV={handleDownloadCSV}
      />

      <ResultModal
        isOpen={modalOpen}
        title={modalTitle}
        logData={logData}
        screenshotUrl={screenshotUrl}
        screenshotFilename={screenshotFilename}
        onClose={() => setModalOpen(false)}
      />
    </>
  );
}

export default App;
