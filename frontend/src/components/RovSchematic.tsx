import React from 'react';
import type { ImuData } from '../types/telemetry';
import { PanelWrapper } from './PanelWrapper';

interface RovSchematicProps {
    imu: ImuData;
}

function rotateVector3(vector: { x: number; y: number; z: number }, yawDeg: number, pitchDeg: number, rollDeg: number) {
    const yaw = yawDeg * Math.PI / 180;
    const pitch = pitchDeg * Math.PI / 180;
    const roll = rollDeg * Math.PI / 180;

    let { x, y, z } = vector;

    const cr = Math.cos(roll), sr = Math.sin(roll);
    [y, z] = [y * cr - z * sr, y * sr + z * cr];

    const cp = Math.cos(pitch), sp = Math.sin(pitch);
    [x, z] = [x * cp + z * sp, -x * sp + z * cp];

    const cy = Math.cos(yaw), sy = Math.sin(yaw);
    [x, y] = [x * cy - y * sy, x * sy + y * cy];

    return { x, y, z };
}

export const RovSchematic: React.FC<RovSchematicProps> = ({ imu }) => {
    const displayYaw = imu.yaw - 90;
    const attitudeTransform = `translate(-50%, -50%) rotateZ(${displayYaw.toFixed(2)}deg) rotateX(${imu.pitch.toFixed(2)}deg) rotateY(${(-imu.roll).toFixed(2)}deg)`;

    // Axis Calculation
    const origin = { x: 52, y: 52 };
    const axisLength = 34;
    const axes = [
        { key: 'x', vector: { x: 1, y: 0, z: 0 } },
        { key: 'y', vector: { x: 0, y: -1, z: 0 } },
        { key: 'z', vector: { x: 0, y: 0, z: 1 } }
    ];

    const renderedAxes = axes.map(axis => {
        const v = rotateVector3(axis.vector, displayYaw, imu.pitch, imu.roll);
        const depthScale = 0.78 + Math.max(-0.22, Math.min(0.22, v.z * 0.18));
        return {
            key: axis.key,
            endX: (origin.x + v.x * axisLength * depthScale).toFixed(1),
            endY: (origin.y + v.y * axisLength * depthScale).toFixed(1),
            labelX: (origin.x + v.x * (axisLength + 10) * depthScale).toFixed(1),
            labelY: (origin.y + v.y * (axisLength + 10) * depthScale).toFixed(1),
            opacity: 0.72 + Math.max(0, v.z) * 0.28,
            strokeWidth: 3.4 + Math.max(0, v.z) * 1.2
        };
    });

    const signedDeg = (val: number) => (val >= 0 ? '+' : '') + val.toFixed(1) + '°';

    return (
        <PanelWrapper className="rov-panel" title="ROV SCHEMATIC — DESIGN VIEW">
            <div id="rov-3d">
                <div className="rov-scene">
                    <div className="rov-grid-plane"></div>
                    <div className="rov-shadow"></div>
                    <div className="rov-model" style={{ transform: attitudeTransform }}>
                        <div className="rov-frame-3d"></div>
                        <div className="rov-body-3d"></div>
                        <div className="rov-nose-3d"></div>
                        <div className="rov-camera-3d"></div>
                        <div className="rov-thruster-3d t1"></div>
                        <div className="rov-thruster-3d t2"></div>
                        <div className="rov-thruster-3d t3"></div>
                        <div className="rov-thruster-3d t4"></div>
                        <div className="rov-thruster-3d t5"></div>
                        <div className="rov-thruster-3d t6"></div>
                        <div className="rov-gripper-3d" aria-label="Front lower gripper">
                            <div className="gripper-mount"></div>
                            <div className="gripper-bar"></div>
                            <div className="gripper-arm upper"></div>
                            <div className="gripper-arm lower"></div>
                            <div className="gripper-claw upper"></div>
                            <div className="gripper-claw lower"></div>
                        </div>
                    </div>
                    <div className="axis-indicator" aria-label="ROV orientation axis indicator">
                        <svg className="axis-svg" viewBox="0 0 104 104" role="img">
                            {renderedAxes.map(axis => (
                                <React.Fragment key={axis.key}>
                                    <line
                                        id={`axis-${axis.key}-line`}
                                        x1="52"
                                        y1="52"
                                        x2={axis.endX}
                                        y2={axis.endY}
                                        style={{ opacity: axis.opacity, strokeWidth: axis.strokeWidth }}
                                    />
                                    <text
                                        id={`axis-${axis.key}-label`}
                                        x={axis.labelX}
                                        y={axis.labelY}
                                        style={{ opacity: axis.opacity }}
                                    >
                                        {axis.key.toUpperCase()}
                                    </text>
                                </React.Fragment>
                            ))}
                            <circle className="axis-origin-svg" cx="52" cy="52" r="4"></circle>
                        </svg>
                    </div>
                    <div className="rov-axis-label">CSS 3D IMU LINK</div>
                </div>
            </div>
            <div className="imu-overlay">
                <div>ROLL <span>{signedDeg(imu.roll)}</span></div>
                <div>PITCH <span>{signedDeg(imu.pitch)}</span></div>
                <div>YAW <span>{imu.yaw.toFixed(1).padStart(5, '0')}°</span></div>
            </div>
        </PanelWrapper>
    );
};
