import { useEffect, useState } from "react";
import { TextField } from "@mui/material";
import { api } from "@api/axios";

interface BackupSchedule {
	enabled: boolean;
	mode: "interval" | "daily";
	interval_hours: number;
	daily_time: string;
	next_run_at: string | null;
	last_run_at: string | null;
	last_error: string | null;
}

function downloadBlob(data: Blob, filename: string) {
	const url = URL.createObjectURL(data);
	const link = document.createElement("a");
	link.href = url;
	link.download = filename;
	link.click();
	setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function formatDate(value: string | null) {
	return value ? new Date(value).toLocaleString("ru-RU") : "—";
}

export const BackupSettings = () => {
	const [schedule, setSchedule] = useState<BackupSchedule | null>(null);
	const [recordingSchedule, setRecordingSchedule] =
		useState<BackupSchedule | null>(null);
	const [upload, setUpload] = useState<File | null>(null);
	const [busy, setBusy] = useState("");
	const [message, setMessage] = useState("");

	useEffect(() => {
		Promise.all([
			api.get<BackupSchedule>("/backup/schedule"),
			api.get<BackupSchedule>("/backup/recordings/schedule"),
		])
			.then(
				([scheduleResponse, recordingScheduleResponse]) => {
					setSchedule(scheduleResponse.data);
					setRecordingSchedule(recordingScheduleResponse.data);
				}
			)
			.catch(() =>
				setMessage("Не удалось загрузить настройки резервного копирования.")
			);
	}, []);

	const downloadDatabase = async () => {
		setBusy("download");
		setMessage("");

		try {
			const response = await api.get<Blob>("/backup/database", {
				responseType: "blob",
			});
			const header = response.headers["content-disposition"] as
				| string
				| undefined;
			const filename =
				header?.match(/filename="?([^";]+)"?/)?.[1] ?? "ai_surveillance.dump";
			downloadBlob(response.data, filename);
		} catch {
			setMessage(
				"Не удалось выгрузить базу данных. Проверьте pg_dump на сервере."
			);
		} finally {
			setBusy("");
		}
	};

	const saveSchedule = async () => {
		if (!schedule) return;

		setBusy("schedule");
		setMessage("");

		try {
			const response = await api.put<BackupSchedule>("/backup/schedule", {
				enabled: schedule.enabled,
				mode: schedule.mode,
				interval_hours: schedule.interval_hours,
				daily_time: schedule.daily_time,
			});
			setSchedule(response.data);
			setMessage("Расписание сохранено.");
		} catch {
			setMessage("Не удалось сохранить расписание.");
		} finally {
			setBusy("");
		}
	};

	const saveRecordingSchedule = async () => {
		if (!recordingSchedule) return;

		setBusy("recording-schedule");
		setMessage("");

		try {
			const response = await api.put<BackupSchedule>(
				"/backup/recordings/schedule",
				{
					enabled: recordingSchedule.enabled,
					mode: recordingSchedule.mode,
					interval_hours: recordingSchedule.interval_hours,
					daily_time: recordingSchedule.daily_time,
				}
			);
			setRecordingSchedule(response.data);
			setMessage("Расписание копирования видеозаписей сохранено.");
		} catch {
			setMessage("Не удалось сохранить расписание видеозаписей.");
		} finally {
			setBusy("");
		}
	};

	const createRecordingBackup = async () => {
		setBusy("recording-create");
		setMessage("");

		try {
			await api.post("/backup/recordings");
			setMessage("Резервная копия видеозаписей создана на сервере.");
		} catch {
			setMessage(
				"Не удалось создать копию. Проверьте, что есть завершённые видеозаписи и доступно место на диске."
			);
		} finally {
			setBusy("");
		}
	};

	const restore = async () => {
		if (!upload) return;

		if (
			!window.confirm(
				"Восстановить базу данных из выбранной копии? Текущие данные БД будут заменены."
			)
		)
			return;

		setBusy("restore");
		setMessage("");

		try {
			const form = new FormData();
			form.append("file", upload);
			await api.post("/backup/restore-upload", form);
			setMessage(
				"База данных восстановлена. Обновите страницу, чтобы загрузить восстановленные данные."
			);
		} catch {
			setMessage(
				"Восстановление не удалось. Проверьте формат .dump и доступность pg_restore на сервере."
			);
		} finally {
			setBusy("");
		}
	};

	return (
		<div style={{ padding: 20, maxWidth: 700, margin: "0 auto" }}>
			<p
				id="backup-copy-title"
				style={{
					marginTop: 0,
					marginBottom: 10,
					fontSize: 18,
					fontWeight: "bold",
				}}
			>
				Резервное копирование базы данных
			</p>
			<section style={cardStyle} aria-labelledby="backup-copy-title">
				<p style={{ marginTop: 0, marginBottom: 10 }}>
					Скачать резервную копию базы данных PostgreSQL в формате .dump.
				</p>
				<button type="button" onClick={downloadDatabase} disabled={!!busy}>
					{busy === "download" ? "Создание копии..." : "Выгрузить базу данных"}
				</button>
			</section>

			<section style={cardStyle} aria-labelledby="backup-schedule-title">
				<h3
					id="backup-schedule-title"
					style={{ marginTop: 0, marginBottom: 12 }}
				>
					Автоматическое расписание сохранения базы данных
				</h3>

				{schedule ? (
					<>
						<label style={{ display: "block", marginBottom: 16 }}>
							<input
								type="checkbox"
								checked={schedule.enabled}
								onChange={(event) =>
									setSchedule({ ...schedule, enabled: event.target.checked })
								}
							/>{" "}
							Включить автоматическое копирование
						</label>
						<div style={{ display: "grid", gap: 16, paddingLeft: 10 }}>
							<label style={{ display: "block" }}>
								<input
									type="radio"
									name="backup-mode"
									checked={schedule.mode === "interval"}
									onChange={() =>
										setSchedule({ ...schedule, mode: "interval" })
									}
								/>{" "}
								Каждые N часов
								<TextField
									label="Интервал, часов"
									type="number"
									size="small"
									value={schedule.interval_hours}
									disabled={schedule.mode !== "interval"}
									sx={{
										display: "flex",
										marginTop: "10px",
										width: 250,
										"& .MuiOutlinedInput-root": { width: "100%" },
									}}
									slotProps={{ htmlInput: { min: 1, max: 720 } }}
									onChange={(event) =>
										setSchedule({
											...schedule,
											interval_hours: Number(event.target.value),
										})
									}
								/>
							</label>
							<label style={{ display: "block" }}>
								<input
									type="radio"
									name="backup-mode"
									checked={schedule.mode === "daily"}
									onChange={() => setSchedule({ ...schedule, mode: "daily" })}
								/>{" "}
								Ежедневно в указанное время
								<TextField
									label="Время сервера"
									type="time"
									size="small"
									value={schedule.daily_time}
									disabled={schedule.mode !== "daily"}
									sx={{
										display: "flex",
										marginTop: "10px",
										width: 250,
										"& .MuiOutlinedInput-root": { width: "100%" },
									}}
									slotProps={{ inputLabel: { shrink: true } }}
									onChange={(event) =>
										setSchedule({ ...schedule, daily_time: event.target.value })
									}
								/>
							</label>
						</div>
						<button
							type="button"
							onClick={saveSchedule}
							disabled={
								!!busy ||
								!Number.isInteger(schedule.interval_hours) ||
								schedule.interval_hours < 1 ||
								schedule.interval_hours > 720 ||
								!/^([01]\d|2[0-3]):[0-5]\d$/.test(schedule.daily_time)
							}
							style={{ marginTop: 16 }}
						>
							Сохранить расписание
						</button>
						<p style={{ marginTop: 10 }}>
							Следующая копия: {formatDate(schedule.next_run_at)}
							<br />
							Последняя копия: {formatDate(schedule.last_run_at)}
						</p>
						{schedule.last_error && (
							<p role="alert" style={{ color: "#b91c1c" }}>
								Последняя ошибка: {schedule.last_error}
							</p>
						)}
					</>
				) : (
					<p>Загрузка расписания...</p>
				)}
			</section>

			<section style={cardStyle} aria-labelledby="backup-upload-title">
				<h3 id="backup-upload-title" style={{ marginTop: 0, marginBottom: 8 }}>
					Восстановление из файла
				</h3>
				<p style={{ marginBottom: 10 }}>
					Выберите ранее скачанный файл PostgreSQL .dump. Восстанавливаются
					данные БД.
				</p>
				<input
					style={{
						display: "block",
						marginBottom: 10,
						width: 250,
						maxWidth: "100%",
					}}
					type="file"
					accept=".dump"
					onChange={(event) => setUpload(event.target.files?.[0] ?? null)}
				/>
				<button
					type="button"
					disabled={!!busy || !upload}
					onClick={() => restore()}
					style={{ display: "block" }}
				>
					Восстановить из файла
				</button>
			</section>

			<p
				id="recording-backup-title"
				style={{
					marginTop: 30,
					marginBottom: 10,
					fontSize: 18,
					fontWeight: "bold",
				}}
			>
				Резервное копирование видеозаписей
			</p>
			<section style={cardStyle} aria-labelledby="recording-backup-title">
				<p style={{ marginBottom: 10 }}>
					ZIP-архив содержит завершённые записи камер из настроенного каталога.
					Копии сохраняются на сервере в saved_backups/recordings.
				</p>
				<button
					style={{ marginBottom: 10 }}
					type="button"
					disabled={!!busy}
					onClick={createRecordingBackup}
				>
					{busy === "recording-create"
						? "Создание копии..."
						: "Создать копию видеозаписей"}
				</button>
			</section>

			<section style={cardStyle} aria-labelledby="recording-schedule-title">
				<h4 style={{ marginBottom: 10 }}>
					Автоматическое расписание сохранения видеозаписей
				</h4>
				{recordingSchedule ? (
					<>
						<label style={{ display: "block", marginBottom: 16 }}>
							<input
								type="checkbox"
								checked={recordingSchedule.enabled}
								onChange={(event) =>
									setRecordingSchedule({
										...recordingSchedule,
										enabled: event.target.checked,
									})
								}
							/>{" "}
							Включить автоматическое копирование видеозаписей
						</label>
						<div style={{ display: "grid", gap: 16, paddingLeft: 10 }}>
							<label style={{ display: "block" }}>
								{" "}
								<input
									type="radio"
									name="recording-backup-mode"
									checked={recordingSchedule.mode === "interval"}
									onChange={() =>
										setRecordingSchedule({
											...recordingSchedule,
											mode: "interval",
										})
									}
								/>{" "}
								Каждые N часов
								<TextField
									label="Интервал, часов"
									type="number"
									size="small"
									value={recordingSchedule.interval_hours}
									disabled={recordingSchedule.mode !== "interval"}
									sx={{
										display: "flex",
										marginTop: "10px",
										width: 250,
										"& .MuiOutlinedInput-root": { width: "100%" },
									}}
									slotProps={{ htmlInput: { min: 1, max: 720 } }}
									onChange={(event) =>
										setRecordingSchedule({
											...recordingSchedule,
											interval_hours: Number(event.target.value),
										})
									}
								/>
							</label>
							<label style={{ display: "block" }}>
								{" "}
								<input
									type="radio"
									name="recording-backup-mode"
									checked={recordingSchedule.mode === "daily"}
									onChange={() =>
										setRecordingSchedule({
											...recordingSchedule,
											mode: "daily",
										})
									}
								/>{" "}
								Ежедневно в указанное время
								<TextField
									label="Время сервера"
									type="time"
									size="small"
									value={recordingSchedule.daily_time}
									disabled={recordingSchedule.mode !== "daily"}
									sx={{
										display: "flex",
										marginTop: "10px",
										width: 250,
										"& .MuiOutlinedInput-root": { width: "100%" },
									}}
									slotProps={{ inputLabel: { shrink: true } }}
									onChange={(event) =>
										setRecordingSchedule({
											...recordingSchedule,
											daily_time: event.target.value,
										})
									}
								/>
							</label>
						</div>
						<button
							type="button"
							onClick={saveRecordingSchedule}
							disabled={
								!!busy ||
								!Number.isInteger(recordingSchedule.interval_hours) ||
								recordingSchedule.interval_hours < 1 ||
								recordingSchedule.interval_hours > 720 ||
								!/^([01]\d|2[0-3]):[0-5]\d$/.test(recordingSchedule.daily_time)
							}
							style={{ marginTop: 16 }}
						>
							Сохранить расписание видеозаписей
						</button>
						<p style={{ marginTop: 10 }}>
							Следующая копия: {formatDate(recordingSchedule.next_run_at)}
							<br />
							Последняя копия: {formatDate(recordingSchedule.last_run_at)}
						</p>
						{recordingSchedule.last_error && (
							<p role="alert" style={{ color: "#b91c1c" }}>
								Последняя ошибка: {recordingSchedule.last_error}
							</p>
						)}
					</>
				) : (
					<p>Загрузка расписания...</p>
				)}

			</section>

			{message && (
				<p role="status" style={{ marginTop: 16 }}>
					{message}
				</p>
			)}
		</div>
	);
};

const cardStyle: React.CSSProperties = {
	border: "1px solid #ddd",
	borderRadius: 8,
	padding: 16,
	marginTop: 24,
};
