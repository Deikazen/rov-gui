import React, { Suspense, useRef, useEffect, useMemo } from "react";
import { Canvas, useLoader, useFrame } from "@react-three/fiber";
import { OrbitControls, Html } from "@react-three/drei";
import { STLLoader } from "three/examples/jsm/loaders/STLLoader.js";
import * as THREE from "three";
import type { ImuData } from "../types/telemetry";
import { PanelWrapper } from "./PanelWrapper";

interface RovStlSchematicProps {
  imu: ImuData;
}

// Sub-komponen untuk memuat & memutar model STL secara realtime
function StlModel({ imu }: { imu: ImuData }) {
  const groupRef = useRef<THREE.Group>(null);
  const imuRef = useRef(imu);

  // Selalu perbarui imuRef setiap kali imu prop berubah
  useEffect(() => {
    imuRef.current = imu;
    if (groupRef.current) {
      const rollRad = (imu.roll * Math.PI) / 180;
      const pitchRad = (imu.pitch * Math.PI) / 180;
      const yawRad = ((imu.yaw - 90) * Math.PI) / 180;
      groupRef.current.rotation.set(pitchRad, yawRad, -rollRad, "YXZ");
    }
  }, [imu]);

  // Load file STL dari folder public (/models/TURTARA2.stl)
  const geometry = useLoader(STLLoader, "/models/TURTARA2.stl");

  // Center bounding box geometri 3D langsung di memori Three.js
  useMemo(() => {
    if (geometry) {
      geometry.center();
    }
  }, [geometry]);

  // Perbarui rotasi di setiap frame 3D (60 FPS) menggunakan imuRef
  useFrame(() => {
    if (groupRef.current) {
      const currentImu = imuRef.current;
      const rollRad = (currentImu.roll * Math.PI) / 180;
      const pitchRad = (currentImu.pitch * Math.PI) / 180;
      const yawRad = ((currentImu.yaw - 90) * Math.PI) / 180;

      groupRef.current.rotation.set(pitchRad, yawRad, -rollRad, "YXZ");
    }
  });

  return (
    <group ref={groupRef}>
      <mesh geometry={geometry} scale={0.005}>
        <meshStandardMaterial
          color="#00f0ff"
          metalness={0.5}
          roughness={0.2}
        />
      </mesh>
    </group>
  );
}

function LoaderFallback() {
  return (
    <Html center>
      <div style={{ color: "#00f0ff", fontFamily: "monospace", fontSize: "12px", whiteSpace: "nowrap" }}>
        LOADING 3D CAD MODEL...
      </div>
    </Html>
  );
}

export const RovStlSchematic: React.FC<RovStlSchematicProps> = ({ imu }) => {
  const signedDeg = (val: number) =>
    (val >= 0 ? "+" : "") + val.toFixed(1) + "°";

  return (
    <PanelWrapper className="rov-panel" title="ROV SCHEMATIC — 3D CAD STL VIEW">
      <div
        id="rov-3d"
        style={{ position: "absolute", inset: 0, width: "100%", height: "100%" }}
      >
        <Canvas camera={{ position: [0, 8, 15], fov: 45 }}>
          <ambientLight intensity={0.8} />
          <directionalLight position={[10, 20, 15]} intensity={1.5} />
          <pointLight
            position={[-10, -10, -10]}
            color="#00f0ff"
            intensity={1}
          />

          <Suspense fallback={<LoaderFallback />}>
            <StlModel imu={imu} />
          </Suspense>

          {/* OrbitControls untuk rotasi/zoom kamera dengan mouse */}
          <OrbitControls enableZoom={true} />
        </Canvas>
      </div>

      {/* Overlay Derajat Telemetri */}
      <div className="imu-overlay">
        <div>
          ROLL <span>{signedDeg(imu.roll)}</span>
        </div>
        <div>
          PITCH <span>{signedDeg(imu.pitch)}</span>
        </div>
        <div>
          YAW <span>{imu.yaw.toFixed(1).padStart(5, "0")}°</span>
        </div>
      </div>
    </PanelWrapper>
  );
};

