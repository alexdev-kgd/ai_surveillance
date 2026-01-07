import { useEffect, useState } from "react";
import { api } from "../api/axios";
interface DetectionSettings {
	shoplift: boolean;
	assault: boolean;
	fall_floor: boolean;
	jump: boolean;
	run: boolean;
	shoot_gun: boolean;
}

interface Settings {
	detection: DetectionSettings;
	sensitivity: number;
}

const defaultSettings: Settings = {
	detection: {
		shoplift: true,
		assault: true,
		fall_floor: true,
		jump: false,
		run: true,
		shoot_gun: true,
	},
	sensitivity: 0.6,
};

export const Settings = () => {
	const [settings, setSettings] = useState<Settings>(defaultSettings);
	const [loading, setLoading] = useState(true);
	const [saving, setSaving] = useState(false);
	const [message, setMessage] = useState("");

	useEffect(() => {
		const fetchSettings = async () => {
			try {
				const res = await api.get("http://127.0.0.1:8000/settings");
				setSettings(res.data);
			} catch (err) {
				console.error(err);
				throw new Error("Failed to fetch");
			} finally {
				setLoading(false);
			}
		};
		fetchSettings();
	}, []);

	const saveSettings = async () => {
		setSaving(true);
		try {
			await api.put("http://127.0.0.1:8000/settings", settings, {
				headers: {
					"Content-Type": "application/json",
				},
			});
			setMessage("Настройки сохранены!");
		} catch (err) {
			console.error(err);
			setMessage("Ошибка при сохранении");
			throw new Error("Failed to save");
		} finally {
			setSaving(false);
			setTimeout(() => setMessage(""), 3000);
		}
	};

	if (loading) return <div>Загрузка настроек...</div>;

	return (
		<div style={{ padding: 20, maxWidth: 600 }}>
			<section style={{ marginBottom: 20 }}>
				<h3>Детекция событий</h3>
				{Object.entries(settings.detection).map(([key, value]) => (
					<label key={key} style={{ display: "block", marginBottom: 8 }}>
						<input
							type="checkbox"
							checked={value}
							onChange={(e) =>
								setSettings({
									...settings,
									detection: { ...settings.detection, [key]: e.target.checked },
								})
							}
						/>
						{" " + key.replace(/([A-Z])/g, " $1")}
					</label>
				))}
			</section>

			<section style={{ marginBottom: 20 }}>
				<h3>Чувствительность модели</h3>
				<input
					type="range"
					min={0}
					max={1}
					step={0.01}
					value={settings.sensitivity}
					onChange={(e) =>
						setSettings({
							...settings,
							sensitivity: parseFloat(e.target.value),
						})
					}
				/>
				<div>{Math.round(settings.sensitivity * 100)}%</div>
			</section>

			<button
				onClick={saveSettings}
				disabled={saving}
				style={{
					padding: "8px 16px",
					backgroundColor: "#007bff",
					color: "white",
					border: "none",
					borderRadius: 4,
					cursor: "pointer",
				}}
			>
				{saving ? "Сохраняем..." : "Сохранить настройки"}
			</button>

			{message && <div style={{ marginTop: 10 }}>{message}</div>}
		</div>
	);
};
