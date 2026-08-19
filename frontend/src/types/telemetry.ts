export interface LogSample {
    timestamp: string;
    altitude: string;
    posX: string;
    posY: string;
    roll: string;
    pitch: string;
    yaw: string;
    qrSide: string;
    connected: number;
}

export interface CameraState {
    duration: number;
    time: number;
    playing: boolean;
}

export interface ImuData {
    roll: number;
    pitch: number;
    yaw: number;
}

export interface Point2D {
    x: number;
    y: number;
}

export interface TrajectoryTelemetry {
    source: 'real' | 'dummy';
    x: number;
    y: number;
    z: number;
    raw_x: number;
    raw_y: number;
    raw_z: number;
    origin_x: number;
    origin_y: number;
    origin_z: number;
    yaw: number;
    mavlink_connected: boolean;
}
