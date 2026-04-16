import { useCallback, useEffect, useRef, useState } from "react";
import { api, baseURL } from "@api/axios";
import type { ICamera } from "@interfaces/camera.interface";
import { useUsbCameraSync } from "@hooks/useUsbCameraSync";
import AddCameraForm from "./AddCameraForm";
import type { StreamMap } from "types/streamMap.type";

function stopStream(stream: MediaStream) {
	stream.getTracks().forEach((track) => track.stop());
}

export const CameraSettings = () => {
	const [cameras, setCameras] = useState<ICamera[]>([]);
	const [loading, setLoading] = useState(true);
	const [activeStreams, setActiveStreams] = useState<StreamMap>({});
	const activeStreamsRef = useRef<StreamMap>({});

	const fetchCameras = useCallback(async () => {
		const res = await api.get<ICamera[]>(`${baseURL}/cameras`);
		setCameras(res.data);
		setLoading(false);
	}, []);

	useUsbCameraSync({ onSynced: fetchCameras });

	useEffect(() => {
		activeStreamsRef.current = activeStreams;
	}, [activeStreams]);

	useEffect(() => {
		fetchCameras();
	}, [fetchCameras]);

	useEffect(() => {
		const cameraIds = new Set(cameras.map((camera) => camera.id));

		setActiveStreams((prev) => {
			const next: StreamMap = {};

			Object.entries(prev).forEach(([cameraId, stream]) => {
				if (cameraIds.has(cameraId)) {
					next[cameraId] = stream;
					return;
				}

				stopStream(stream);
			});

			return next;
		});
	}, [cameras]);

	useEffect(() => {
		return () => {
			Object.values(activeStreamsRef.current).forEach((stream) =>
				stopStream(stream)
			);
		};
	}, []);

	const startUsbStream = useCallback(async (camera: ICamera) => {
		if (camera.type !== "USB" || !camera.device_id) return;

		const stream = await navigator.mediaDevices.getUserMedia({
			video: { deviceId: { exact: camera.device_id } },
			audio: false,
		});

		setActiveStreams((prev) => {
			const existing = prev[camera.id];

			if (existing) {
				stopStream(stream);
				return prev;
			}

			return { ...prev, [camera.id]: stream };
		});
	}, []);

	const stopUsbStream = useCallback((cameraId: string) => {
		setActiveStreams((prev) => {
			const stream = prev[cameraId];
			if (!stream) return prev;

			stopStream(stream);

			const next: StreamMap = { ...prev };
			delete next[cameraId];

			return next;
		});
	}, []);

	const toggleCamera = async (id: string) => {
		const camera = cameras.find((item) => item.id === id);
		if (!camera) return;

		const res = await api.patch<{ id: string; enabled: boolean }>(
			`${baseURL}/cameras/${id}/toggle`
		);
		const enabled = res.data.enabled;

		setCameras((prev) =>
			prev.map((item) => (item.id === id ? { ...item, enabled } : item))
		);

		if (camera.type === "USB") {
			if (enabled) {
				await startUsbStream(camera);
			} else {
				stopUsbStream(id);
			}
		}
	};

	const removeCamera = async (id: string) => {
		await api.delete(`${baseURL}/cameras/${id}`);
		stopUsbStream(id);
		setCameras((prev) => prev.filter((camera) => camera.id !== id));
	};

	if (loading) return <div>Загрузка камер...</div>;

	return (
		<div style={{ padding: 20, maxWidth: 600 }}>
			<h2>Список камер</h2>

			{cameras.map((camera) => (
				<div
					key={camera.id}
					style={{
						border: "1px solid #ddd",
						borderRadius: 6,
						padding: 10,
						marginBottom: 10,
					}}
				>
					<div
						style={{
							opacity: camera.enabled ? 1 : 0.5,
							pointerEvents: camera.enabled ? "auto" : "none",
						}}
					>
						<strong>{camera.name}</strong>
						<div style={{ fontSize: 12 }}>
							Тип: {camera.type === "USB" ? "USB webcam" : "RTSP"}
						</div>
						<div style={{ fontSize: 12 }}>
							{camera.type === "USB"
								? `ID Устройства: ${camera.device_id ?? "n/a"}`
								: camera.rtsp}
						</div>
					</div>

					<button
						style={{ marginTop: 6 }}
						onClick={() => toggleCamera(camera.id)}
					>
						{camera.enabled ? "Выключить" : "Включить"}
					</button>

					<button
						style={{ marginTop: 6, marginLeft: 8 }}
						onClick={() => removeCamera(camera.id)}
					>
						Удалить
					</button>
				</div>
			))}

			<hr style={{ margin: "30px 0" }} />

			<AddCameraForm
				onAdded={(camera) => setCameras((prev) => [...prev, camera])}
			/>
		</div>
	);
};
