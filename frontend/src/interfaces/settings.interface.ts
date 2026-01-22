export interface IActionSetting {
	enabled: boolean;
	sensitivity: number;
}

export interface ISettings {
	detection: Record<string, IActionSetting>;
	useObjectDetection: boolean;
}
