import { useCallback, useEffect } from "react";
import { api, baseURL } from "@api/axios";
import type {
	IUsbSyncPayload,
	IUsbVideoInput,
} from "@interfaces/usbCamera.interface";

interface UseUsbCameraSyncOptions {
	onSynced?: () => Promise<void> | void;
}

const VIDEO_INPUT_KIND = "videoinput";

async function enumerateUsbVideoInputs(): Promise<IUsbVideoInput[]> {
	const devices = await navigator.mediaDevices.enumerateDevices();
	const videoInputs = devices.filter(
		(device): device is MediaDeviceInfo =>
			device.kind === VIDEO_INPUT_KIND && device.deviceId.trim().length > 0
	);

	return videoInputs.map((device, index) => ({
		deviceId: device.deviceId,
		label: device.label.trim() || `USB Camera ${index + 1}`,
	}));
}

export function useUsbCameraSync({ onSynced }: UseUsbCameraSyncOptions) {
	const syncUsbCameras = useCallback(async () => {
		if (!navigator.mediaDevices?.enumerateDevices) {
			return;
		}

		const usbInputs = await enumerateUsbVideoInputs();
		const payload: IUsbSyncPayload = { devices: usbInputs };

		await api.post(`${baseURL}/cameras/usb/sync`, payload);
		await onSynced?.();
	}, [onSynced]);

	useEffect(() => {
		let mounted = true;

		const syncIfMounted = async () => {
			if (!mounted) return;
			await syncUsbCameras();
		};

		syncIfMounted();
		navigator.mediaDevices?.addEventListener("devicechange", syncIfMounted);

		return () => {
			mounted = false;
			navigator.mediaDevices?.removeEventListener(
				"devicechange",
				syncIfMounted
			);
		};
	}, [syncUsbCameras]);

	return { syncUsbCameras };
}
