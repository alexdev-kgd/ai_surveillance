import { useEffect, useState } from "react";
import { api } from "../api/axios";
interface ActionSetting {
	enabled: boolean;
	sensitivity: number;
}

interface Settings {
	detection: Record<string, ActionSetting>;
}

const defaultSettings: Settings = {
	detection: {
		shoplift: { enabled: true, sensitivity: 0.7 },
		assault: { enabled: true, sensitivity: 0.8 },
		fall_floor: { enabled: true, sensitivity: 0.6 },
		jump: { enabled: false, sensitivity: 0.5 },
		run: { enabled: true, sensitivity: 0.65 },
		shoot_gun: { enabled: true, sensitivity: 0.9 },
	},
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
			} finally {
				setLoading(false);
			}
		};
		fetchSettings();
	}, []);

	const updateAction = (actionKey: string, patch: Partial<ActionSetting>) => {
		setSettings((prev) => ({
			...prev,
			detection: {
				...prev.detection,
				[actionKey]: {
					...prev.detection[actionKey],
					...patch,
				},
			},
		}));
	};

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
		} finally {
			setSaving(false);
			setTimeout(() => setMessage(""), 3000);
		}
	};

	if (loading) return <div>Загрузка настроек...</div>;

	return (
		<div style={{ padding: 20, maxWidth: 600 }}>
			<h2 style={{ marginBottom: 20 }}>Настройки детекции</h2>

			{Object.entries(settings.detection).map(([key, action]) => (
				<div
					key={key}
					style={{
						marginBottom: 20,
						padding: 10,
						border: "1px solid #ddd",
						borderRadius: 6,
					}}
				>
					<label style={{ display: "block", marginBottom: 6 }}>
						<input
							type="checkbox"
							checked={action.enabled}
							onChange={(e) => updateAction(key, { enabled: e.target.checked })}
						/>{" "}
						<strong>{key.replace(/_/g, " ")}</strong>
					</label>

					<input
						type="range"
						min="0"
						max="1"
						step="0.01"
						value={action.sensitivity}
						disabled={!action.enabled}
						onChange={(e) =>
							updateAction(key, {
								sensitivity: Number(e.target.value),
							})
						}
						style={{ width: "100%" }}
					/>

					<div style={{ fontSize: 12, opacity: 0.7 }}>
						Чувствительность: {action.sensitivity.toFixed(2)}
					</div>
				</div>
			))}
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
