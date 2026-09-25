export interface ILiveDetection {
	frame: number;
	label: string;
	confidence: number;
	bbox?: number[];
}

export interface ILiveCameraFrameMessage {
	frame?: string;
	detections: ILiveDetection[];
	frameIndex?: number;
	sourceWidth?: number;
	sourceHeight?: number;
	analysisFps?: number;
	analysisMs?: number;
	droppedFrames?: number;
}
