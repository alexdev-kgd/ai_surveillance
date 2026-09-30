import { useEffect, useState } from "react";
import { TextField } from "@mui/material";
import { api } from "@api/axios";
import type { ICamera } from "@interfaces/camera.interface";

interface IRecordingSettings {
	enabled: boolean;
	clip_limit_mode: "size" | "duration";
	max_clip_size_mb: number;
	max_clip_duration_seconds: number;
	camera_enabled: Record<string, boolean>;
	directory: string;
}

export const RecordingSettings = () => {
	const [settings, setSettings] = useState<IRecordingSettings | null>(null);
	const [cameras, setCameras] = useState<ICamera[]>([]);
	const [saving, setSaving] = useState(false);
	const [message, setMessage] = useState("");

	useEffect(() => {
		Promise.all([
			api.get<IRecordingSettings>("/recording"),
			api.get<ICamera[]>("/cameras"),
		])
			.then(([recording, cameraList]) => {
				setSettings(recording.data);
				setCameras(cameraList.data);
			})
			.catch(() => setMessage("Не удалось загрузить настройки видеозаписи."));
	}, []);

	const save = async () => {
		if (!settings) return;
		setSaving(true);
		setMessage("");
		try {
			const response = await api.put<IRecordingSettings>("/recording", {
				...settings,
				directory: settings.directory.trim(),
			});
			setSettings(response.data);
			setMessage("Настройки видеозаписи сохранены.");
		} catch {
			setMessage("Не удалось сохранить настройки видеозаписи.");
		} finally {
			setSaving(false);
		}
	};

	if (!settings)
		return (
			<div style={{ padding: 20 }}>{message || "Загрузка настроек..."}</div>
		);

	return (
		<div style={{ padding: 20, maxWidth: 600, margin: "0 auto" }}>
			<h2>Видеозапись</h2>
			<label>
				<input
					type="checkbox"
					checked={settings.enabled}
					onChange={(event) =>
						setSettings({ ...settings, enabled: event.target.checked })
					}
				/>{" "}
				Записывать видео с камер
			</label>
			<div style={{ marginTop: 20 }}>
				<TextField
					label="Каталог сохранения"
					value={settings.directory}
					size="small"
					fullWidth
					onChange={(event) =>
						setSettings({ ...settings, directory: event.target.value })
					}
					sx={{ marginBottom: "10px" }}
				/>
				<p style={{ marginTop: 0 }}>
					Относительный путь считается от корня проекта. В выбранном каталоге
					создаются папки камер.
				</p>
			</div>
			<fieldset
				style={{
					marginTop: 20,
					marginBottom: 10,
					padding: 10,
					border: "1px solid #ddd",
					borderRadius: 6,
				}}
			>
				<legend>Ограничение одного клипа</legend>
				<label style={{ display: "block", marginLeft: 10, marginBottom: 16 }}>
					<input
						type="radio"
						name="clip-limit"
						checked={settings.clip_limit_mode === "size"}
						onChange={() =>
							setSettings({ ...settings, clip_limit_mode: "size" })
						}
						style={{ marginRight: 8 }}
					/>{" "}
					Максимальный размер, МБ
					<TextField
						label="Максимальный размер одного клипа, МБ"
						type="number"
						size="small"
						value={settings.max_clip_size_mb}
						disabled={settings.clip_limit_mode !== "size"}
						slotProps={{ htmlInput: { min: 1, max: 2048 } }}
						onChange={(event) =>
							setSettings({
								...settings,
								max_clip_size_mb: Number(event.target.value),
							})
						}
						sx={{
							display: "flex",
							marginTop: "10px",
							width: 250,
							"& .MuiOutlinedInput-root": { width: "100%" },
						}}
					/>
				</label>
				<label style={{ display: "block", marginLeft: 10 }}>
					<input
						type="radio"
						name="clip-limit"
						checked={settings.clip_limit_mode === "duration"}
						onChange={() =>
							setSettings({ ...settings, clip_limit_mode: "duration" })
						}
						style={{ marginRight: 8 }}
					/>{" "}
					Максимальная продолжительность, секунд
					<TextField
						label="Максимальная продолжительность одного клипа, секунд"
						type="number"
						size="small"
						value={settings.max_clip_duration_seconds}
						disabled={settings.clip_limit_mode !== "duration"}
						slotProps={{ htmlInput: { min: 1, max: 86400 } }}
						onChange={(event) =>
							setSettings({
								...settings,
								max_clip_duration_seconds: Number(event.target.value),
							})
						}
						sx={{
							display: "flex",
							marginTop: "10px",
							width: 250,
							"& .MuiOutlinedInput-root": { width: "100%" },
						}}
					/>
				</label>
			</fieldset>
			<h3 style={{ marginTop: 0 }}>Запись по камерам</h3>
			{cameras.map((camera) => (
				<label key={camera.id} style={{ display: "block", marginBottom: 8 }}>
					<input
						type="checkbox"
						checked={settings.camera_enabled[camera.id] ?? true}
						onChange={(event) =>
							setSettings({
								...settings,
								camera_enabled: {
									...settings.camera_enabled,
									[camera.id]: event.target.checked,
								},
							})
						}
					/>{" "}
					{camera.name}
					{!camera.enabled ? " (камера выключена)" : ""}
				</label>
			))}
			<button
				disabled={
					saving ||
					!settings.directory.trim() ||
					!Number.isInteger(settings.max_clip_size_mb) ||
					settings.max_clip_size_mb < 1 ||
					settings.max_clip_size_mb > 2048 ||
					!Number.isInteger(settings.max_clip_duration_seconds) ||
					settings.max_clip_duration_seconds < 1 ||
					settings.max_clip_duration_seconds > 86400
				}
				onClick={save}
			>
				{saving ? "Сохранение..." : "Сохранить"}
			</button>
			{message && <p role="status">{message}</p>}
		</div>
	);
};
