import { useCallback, useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import { TextField } from "@mui/material";
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
	const [editingCameraId, setEditingCameraId] = useState<string | null>(null);
	const [editName, setEditName] = useState("");
	const [editRtsp, setEditRtsp] = useState("");
	const [saving, setSaving] = useState(false);
	const [editError, setEditError] = useState("");
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

	const startEditing = (camera: ICamera) => {
		setEditingCameraId(camera.id);
		setEditName(camera.name);
		setEditRtsp(camera.rtsp);
		setEditError("");
	};

	const saveCamera = async (
		event: FormEvent<HTMLFormElement>,
		camera: ICamera
	) => {
		event.preventDefault();
		const name = editName.trim();
		const rtsp = editRtsp.trim();
		if (!name || (camera.type === "IP" && !rtsp)) {
			setEditError("Заполните название и URL камеры.");
			return;
		}

		setSaving(true);
		setEditError("");
		try {
			const res = await api.patch<ICamera>(`${baseURL}/cameras/${camera.id}`, {
				name,
				...(camera.type === "IP" ? { rtsp } : {}),
			});
			setCameras((prev) =>
				prev.map((item) => (item.id === camera.id ? res.data : item))
			);
			setEditingCameraId(null);
		} catch (error) {
			console.error(error);
			setEditError("Не удалось сохранить изменения камеры.");
		} finally {
			setSaving(false);
		}
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
					{editingCameraId === camera.id && (
						<form
							onSubmit={(event) => saveCamera(event, camera)}
							style={{ display: "grid", gap: 12, marginTop: 12 }}
						>
							<TextField
								label="Название камеры"
								value={editName}
								onChange={(event) => setEditName(event.target.value)}
								size="small"
								fullWidth
								required
							/>
							{camera.type === "IP" && (
								<TextField
									label="RTSP URL"
									value={editRtsp}
									onChange={(event) => setEditRtsp(event.target.value)}
									size="small"
									fullWidth
									required
								/>
							)}
							{editError && <div role="alert">{editError}</div>}
							<div>
								<button type="submit" disabled={saving}>
									Сохранить
								</button>
								<button
									type="button"
									disabled={saving}
									onClick={() => setEditingCameraId(null)}
									style={{ marginLeft: 8 }}
								>
									Отмена
								</button>
							</div>
						</form>
					)}

					{editingCameraId !== camera.id && (
						<div>
							<button
							style={{ marginTop: 6 }}
								onClick={() => toggleCamera(camera.id)}
							>
								{camera.enabled ? "Выключить" : "Включить"}
							</button>
							<button
							style={{ marginTop: 6, marginLeft: 8 }}
								onClick={() => startEditing(camera)}
							>
								Редактировать
						</button>
							<button
							style={{ marginTop: 6, marginLeft: 8 }}
								onClick={() => removeCamera(camera.id)}
							>
								Удалить
							</button>
						</div>
					)}
				</div>
			))}

			<hr style={{ margin: "30px 0" }} />

			<AddCameraForm
				onAdded={(camera) => setCameras((prev) => [...prev, camera])}
			/>
		</div>
	);
};
