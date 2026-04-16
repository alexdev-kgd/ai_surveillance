import { useState, useEffect } from "react";
import { api, baseURL } from "@api/axios";
import type { IActionSetting, ISettings } from "@interfaces/settings.interface";

const defaultSettings: ISettings = {
	detection: {
		shoplift: { enabled: true, sensitivity: 0.7 },
		assault: { enabled: true, sensitivity: 0.8 },
		fall_floor: { enabled: true, sensitivity: 0.6 },
		jump: { enabled: false, sensitivity: 0.5 },
		run: { enabled: true, sensitivity: 0.65 },
		shoot_gun: { enabled: true, sensitivity: 0.9 },
	},
	useObjectDetection: true,
};

export const DetectionSettings = () => {
	const [settings, setSettings] = useState<ISettings>(defaultSettings);
	const [saving, setSaving] = useState(false);
	const [loading, setLoading] = useState(true);
	const [message, setMessage] = useState("");

	const updateAction = (actionKey: string, patch: Partial<IActionSetting>) => {
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

	useEffect(() => {
		const controller = new AbortController();

		const fetchSettings = async () => {
			try {
				const res = await api.get(`${baseURL}/settings`, {
					signal: controller.signal,
				});
				setSettings(res.data);
			} catch (err) {
				console.error(err);
			} finally {
				setLoading(false);
			}
		};

		fetchSettings();

		return () => controller.abort();
	}, []);

	const saveSettings = async () => {
		setSaving(true);
		try {
			await api.put(`${baseURL}/settings`, settings, {
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

	const toggleObjectDetection = (enabled: boolean) => {
		setSettings((prev) => ({
			...prev,
			useObjectDetection: enabled,
		}));
	};

	if (loading) return <div>Загрузка настроек...</div>;

	return (
		<div style={{ padding: 20, maxWidth: 600 }}>
			<div>
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
								onChange={(e) =>
									updateAction(key, { enabled: e.target.checked })
								}
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
			</div>

			{/* YOLO SWITCH */}
			<div style={{ marginTop: 50 }}>
				<label style={{ display: "block", marginBottom: 0 }}>
					<input
						type="checkbox"
						checked={settings.useObjectDetection}
						onChange={(e) => toggleObjectDetection(e.target.checked)}
					/>{" "}
					Использовать детекцию объектов (YOLO)
				</label>

				<p style={{ fontSize: 13, color: "#666" }}>
					Если выключено, анализ проводится по всей сцене целиком. Подходит для
					выявления массовых и контекстных аномалий.
				</p>
			</div>

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
					marginTop: 50,
				}}
			>
				{saving ? "Сохраняем..." : "Сохранить"}
			</button>

			{message && <div style={{ marginTop: 10 }}>{message}</div>}
		</div>
	);
};
