export interface ILiveDetectionEvent {
	id: string;
	cameraId: string;
	cameraName: string;
	frame: number;
	label: string;
	confidence: number;
	timeSec: number;
	detectedAt: string;
}
