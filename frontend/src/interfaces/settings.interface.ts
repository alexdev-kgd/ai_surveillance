export interface IActionSetting {
	enabled: boolean;
	sensitivity: number;
}

export interface ISettings {
	detection: Record<string, IActionSetting>;
	roles: Record<string, string[]>;
}
