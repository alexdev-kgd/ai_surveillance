export interface IUsbVideoInput {
	deviceId: string;
	label: string;
}

export interface IUsbSyncPayload {
	devices: IUsbVideoInput[];
}
