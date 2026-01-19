export interface IDetection {
	id: number;
	frame: number;
	label: string;
	confidence: number;
	bbox: number[];
}
