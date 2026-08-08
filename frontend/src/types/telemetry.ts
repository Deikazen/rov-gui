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
