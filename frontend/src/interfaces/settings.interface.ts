export interface IActionSetting {
	enabled: boolean;
	/** Display sensitivity (on-screen labels). Higher → easier to show. */
	sensitivity: number;
	/**
	 * Alert sensitivity for events/notifications.
	 * Typically lower than sensitivity (stricter). Optional for older settings.
	 */
	alert_sensitivity?: number;
}

export interface ISettings {
	detection: Record<string, IActionSetting>;
	useObjectDetection: boolean;
}
