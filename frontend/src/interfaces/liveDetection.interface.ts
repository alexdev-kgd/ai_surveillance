export interface ILiveDetection {
	frame: number;
	label: string;
	confidence: number;
	bbox?: number[];
}

export interface ILiveCameraFrameMessage {
	frame: string;
	detections: ILiveDetection[];
}
