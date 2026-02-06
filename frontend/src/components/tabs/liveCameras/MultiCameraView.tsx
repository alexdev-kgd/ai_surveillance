import type { ICamera, ICameraConfig } from "@interfaces/camera.interface";
import CameraTile from "./CameraTile";
import { api, baseURL } from "@api/axios";
import { useState, useEffect } from "react";

export default function MultiCameraView() {
	const [cameras, setCameras] = useState<ICameraConfig[]>([]);
	const [loading, setLoading] = useState(true);

	useEffect(() => {
		const fetchCameras = async () => {
			const res = await api.get<ICamera[]>(`${baseURL}/cameras`);

			const mapped: ICameraConfig[] = res.data
				.filter((c) => c.enabled)
				.map((c) => ({
					id: c.id,
					name: c.name,
					source: c.type,
					wsPath: `/video/${c.id}`,
					deviceId: c.device_id ?? undefined,
				}));

			setCameras(mapped);
			setLoading(false);
		};

		fetchCameras();
	}, []);

	if (loading) return <div>Загрузка камер...</div>;

	if (!cameras.length) return <div>Нет подключённых камер</div>;

	return (
		<div
			style={{
				display: "grid",
				gridTemplateColumns: "repeat(auto-fit, minmax(360px, 1fr))",
				gap: 16,
			}}
		>
			{cameras.map((cam) => (
				<CameraTile key={cam.id} camera={cam} />
			))}
		</div>
	);
}
