import type { CameraSource } from "types/cameraSource.type";

export interface ICameraConfig {
	id: string;
	name: string;
	source: CameraSource;
	wsPath: string; // /video/webcam-1, /video/ip-1
	deviceId?: string;
}

export interface ICamera {
	id: string;
	name: string;
	type: "IP" | "USB";
	rtsp: string;
	enabled: boolean;
	device_id?: string | null;
}
