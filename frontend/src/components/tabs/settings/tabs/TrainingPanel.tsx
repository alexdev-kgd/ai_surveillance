import { useEffect, useMemo, useState } from "react";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import {
	Accordion,
	AccordionDetails,
	AccordionSummary,
	LinearProgress,
	MenuItem,
	TextField,
} from "@mui/material";
import { api } from "@api/axios";
import { useDebounce } from "@hooks/useDebounce";
import type {
	IDatasetScan,
	ITrainingClass,
	ITrainingDefaults,
	ITrainingStartRequest,
	ITrainingStatus,
} from "@interfaces/training.interface";

const emptyDefaults: ITrainingDefaults = {
	train_dir: "dataset/train",
	val_dir: "dataset/val",
	yolo_train_dir: "dataset-cropped/train",
	yolo_val_dir: "dataset-cropped/val",
	train_scene_model: true,
	train_yolo_model: true,
	prepare_yolo_crops: true,
	plot_dir: "fine-tune/training_plots",
	epochs: 40,
	backbone_lr: 1e-5,
	head_lr: 1e-4,
	batch_size: 4,
	weight_decay: 5e-3,
	dropout: 0.65,
	label_smoothing: 0.1,
	patience: 3,
	fusion: "add",
	use_class_weights: true,
};

const runningStates = new Set(["precomputing", "cropping", "training"]);

function formatMetric(value?: number | null) {
	return typeof value === "number" && Number.isFinite(value)
		? value.toFixed(4)
		: "-";
}

function progressValue(status: ITrainingStatus | null) {
	if (!status || status.total <= 0) return 0;
	return Math.max(0, Math.min(100, (status.current / status.total) * 100));
}

function isAbortError(error: unknown) {
	if (typeof error !== "object" || error === null) return false;
	const name = "name" in error ? String(error.name) : "";
	const code = "code" in error ? String(error.code) : "";
	return (
		name === "CanceledError" || name === "AbortError" || code === "ERR_CANCELED"
	);
}

function axiosErrorMessage(error: unknown, fallback: string) {
	if (
		typeof error === "object" &&
		error !== null &&
		"response" in error &&
		typeof (error as { response?: { data?: { detail?: string } } }).response
			?.data?.detail === "string"
	) {
		return (error as { response: { data: { detail: string } } }).response.data
			.detail;
	}
	return fallback;
}

export const TrainingPanel = () => {
	const [defaults, setDefaults] = useState<ITrainingDefaults>(emptyDefaults);
	const [trainDir, setTrainDir] = useState(emptyDefaults.train_dir);
	const [valDir, setValDir] = useState(emptyDefaults.val_dir);
	const [yoloTrainDir, setYoloTrainDir] = useState(
		emptyDefaults.yolo_train_dir
	);
	const [yoloValDir, setYoloValDir] = useState(emptyDefaults.yolo_val_dir);
	const [trainSceneModel, setTrainSceneModel] = useState(
		emptyDefaults.train_scene_model
	);
	const [trainYoloModel, setTrainYoloModel] = useState(
		emptyDefaults.train_yolo_model
	);
	const [prepareYoloCrops, setPrepareYoloCrops] = useState(
		emptyDefaults.prepare_yolo_crops
	);
	const [savePlots, setSavePlots] = useState(false);
	const [plotDir, setPlotDir] = useState(emptyDefaults.plot_dir);
	const [epochs, setEpochs] = useState(emptyDefaults.epochs);
	const [backboneLr, setBackboneLr] = useState(
		String(emptyDefaults.backbone_lr)
	);
	const [headLr, setHeadLr] = useState(String(emptyDefaults.head_lr));
	const [batchSize, setBatchSize] = useState(emptyDefaults.batch_size);
	const [weightDecay, setWeightDecay] = useState(
		String(emptyDefaults.weight_decay)
	);
	const [dropout, setDropout] = useState(String(emptyDefaults.dropout));
	const [labelSmoothing, setLabelSmoothing] = useState(
		String(emptyDefaults.label_smoothing)
	);
	const [patience, setPatience] = useState(emptyDefaults.patience);
	const [fusion, setFusion] = useState(emptyDefaults.fusion);
	const [useClassWeights, setUseClassWeights] = useState(
		emptyDefaults.use_class_weights
	);
	const [classes, setClasses] = useState<ITrainingClass[]>([]);
	const [scanError, setScanError] = useState("");
	const [scanLoading, setScanLoading] = useState(false);
	const [status, setStatus] = useState<ITrainingStatus | null>(null);
	const [actionError, setActionError] = useState("");
	const [defaultsReady, setDefaultsReady] = useState(false);

	const debouncedTrainDir = useDebounce(trainDir, 400);
	const debouncedValDir = useDebounce(valDir, 400);
	const debouncedYoloTrainDir = useDebounce(yoloTrainDir, 400);
	const debouncedYoloValDir = useDebounce(yoloValDir, 400);
	const running = runningStates.has(status?.state ?? "");

	const applyDefaults = (next: ITrainingDefaults) => {
		setDefaults(next);
		setTrainDir(next.train_dir);
		setValDir(next.val_dir);
		setYoloTrainDir(next.yolo_train_dir);
		setYoloValDir(next.yolo_val_dir);
		setTrainSceneModel(next.train_scene_model);
		setTrainYoloModel(next.train_yolo_model);
		setPrepareYoloCrops(next.prepare_yolo_crops);
		setPlotDir(next.plot_dir);
		setEpochs(next.epochs);
		setBackboneLr(String(next.backbone_lr));
		setHeadLr(String(next.head_lr));
		setBatchSize(next.batch_size);
		setWeightDecay(String(next.weight_decay));
		setDropout(String(next.dropout));
		setLabelSmoothing(String(next.label_smoothing));
		setPatience(next.patience);
		setFusion(next.fusion);
		setUseClassWeights(next.use_class_weights);
	};

	useEffect(() => {
		const controller = new AbortController();
		api
			.get<ITrainingStatus>("/training/status", { signal: controller.signal })
			.then((response) => {
				setStatus(response.data);
				applyDefaults(response.data.defaults);
				setActionError("");
				setDefaultsReady(true);
			})
			.catch((error) => {
				if (isAbortError(error)) return;
				setDefaultsReady(true);
				setActionError("Не удалось загрузить состояние обучения");
			});
		return () => controller.abort();
	}, []);

	useEffect(() => {
		if (!running) return;
		const timer = window.setInterval(() => {
			api
				.get<ITrainingStatus>("/training/status")
				.then((response) => setStatus(response.data))
				.catch(() => undefined);
		}, 1000);
		return () => window.clearInterval(timer);
	}, [running]);

	useEffect(() => {
		if (!defaultsReady) return;
		const controller = new AbortController();
		setScanLoading(true);
		api
			.get<IDatasetScan>("/training/classes", {
				params: {
					train_dir: debouncedTrainDir,
					val_dir: debouncedValDir,
					yolo_train_dir: debouncedYoloTrainDir,
					yolo_val_dir: debouncedYoloValDir,
				},
				signal: controller.signal,
			})
			.then((response) => {
				setScanError(response.data.error || "");
				setClasses((prev) => {
					const previousLabels = Object.fromEntries(
						prev.map((item) => [item.key, item.label])
					);
					return response.data.classes.map((item) => ({
						...item,
						label: previousLabels[item.key] || item.label,
					}));
				});
			})
			.catch((error) => {
				if (isAbortError(error)) return;
				setScanError("Не удалось прочитать папки выборок");
				setClasses([]);
			})
			.finally(() => {
				if (!controller.signal.aborted) setScanLoading(false);
			});
		return () => controller.abort();
	}, [
		debouncedTrainDir,
		debouncedValDir,
		debouncedYoloTrainDir,
		debouncedYoloValDir,
		defaultsReady,
	]);

	const missingValClasses = useMemo(
		() => classes.filter((item) => trainSceneModel && !item.has_val),
		[classes, trainSceneModel]
	);
	const missingYoloValClasses = useMemo(
		() =>
			classes.filter(
				(item) => trainYoloModel && !prepareYoloCrops && !item.has_yolo_val
			),
		[classes, trainYoloModel, prepareYoloCrops]
	);

	const updateClassLabel = (key: string, label: string) => {
		setClasses((prev) =>
			prev.map((item) => (item.key === key ? { ...item, label } : item))
		);
	};

	const buildPayload = (): ITrainingStartRequest => ({
		train_dir: trainDir.trim(),
		val_dir: valDir.trim(),
		yolo_train_dir: yoloTrainDir.trim(),
		yolo_val_dir: yoloValDir.trim(),
		train_scene_model: trainSceneModel,
		train_yolo_model: trainYoloModel,
		prepare_yolo_crops: prepareYoloCrops,
		save_plots: savePlots,
		plot_dir: savePlots ? plotDir.trim() : null,
		classes: classes.map((item) => ({
			key: item.key,
			label: item.label.trim() || item.key,
		})),
		epochs,
		backbone_lr: Number(backboneLr),
		head_lr: Number(headLr),
		batch_size: batchSize,
		weight_decay: Number(weightDecay),
		dropout: Number(dropout),
		label_smoothing: Number(labelSmoothing),
		patience,
		fusion,
		use_class_weights: useClassWeights,
	});

	const startTraining = async () => {
		setActionError("");
		try {
			const response = await api.post<ITrainingStatus>(
				"/training/start",
				buildPayload()
			);
			setStatus(response.data);
		} catch (error) {
			setActionError(axiosErrorMessage(error, "Не удалось запустить обучение"));
		}
	};

	const cancelTraining = async () => {
		setActionError("");
		try {
			const response = await api.post<ITrainingStatus>("/training/cancel");
			setStatus(response.data);
		} catch (error) {
			setActionError(axiosErrorMessage(error, "Не удалось отменить обучение"));
		}
	};

	const canStart =
		!running &&
		!scanLoading &&
		classes.length > 0 &&
		(trainSceneModel || trainYoloModel) &&
		(!(trainSceneModel || (trainYoloModel && prepareYoloCrops)) ||
			(Boolean(trainDir.trim()) && Boolean(valDir.trim()))) &&
		(!trainYoloModel ||
			(Boolean(yoloTrainDir.trim()) && Boolean(yoloValDir.trim()))) &&
		(!savePlots || Boolean(plotDir.trim())) &&
		Number(backboneLr) > 0 &&
		Number(headLr) > 0;

	return (
		<div style={{ marginTop: 36 }}>
			<hr
				style={{
					border: "none",
					borderTop: "1px solid #ddd",
					marginBottom: 24,
				}}
			/>
			<h2 style={{ marginBottom: 8 }}>Обучение модели</h2>
			<p
				style={{ fontSize: 13, color: "#666", marginTop: 0, marginBottom: 12 }}
			>
				Классы действий определяются по папкам внутри тренировочной выборки.
				Каждая папка - отдельный класс.
			</p>

			<h3 style={{ marginBottom: 8 }}>Полная сцена</h3>
			<label style={{ display: "block", marginBottom: 0 }}>
				<input
					type="checkbox"
					checked={trainSceneModel}
					disabled={running}
					onChange={(event) => setTrainSceneModel(event.target.checked)}
				/>{" "}
				Обучать модель полной сцены
			</label>
			<p
				style={{ fontSize: 13, color: "#666", marginTop: 8, marginBottom: 12 }}
			>
				Если включено, модель учится на целых кадрах и используется, когда
				детекция YOLO выключена.
			</p>
			<TextField
				label="Папка с тренировочными данными (сцены)"
				value={trainDir}
				size="small"
				fullWidth
				disabled={
					running || (!trainSceneModel && !(trainYoloModel && prepareYoloCrops))
				}
				onChange={(event) => setTrainDir(event.target.value)}
				helperText="Путь на сервере. Относительный путь считается от каталога backend."
				sx={{ marginBottom: "16px" }}
			/>
			<TextField
				label="Папка с валидационными данными (сцены)"
				value={valDir}
				size="small"
				fullWidth
				disabled={
					running || (!trainSceneModel && !(trainYoloModel && prepareYoloCrops))
				}
				onChange={(event) => setValDir(event.target.value)}
				sx={{ marginBottom: "20px" }}
			/>

			<h3 style={{ marginBottom: 8 }}>Вырезки людей (YOLO)</h3>
			<label style={{ display: "block", marginBottom: 0 }}>
				<input
					type="checkbox"
					checked={trainYoloModel}
					disabled={running}
					onChange={(event) => setTrainYoloModel(event.target.checked)}
				/>{" "}
				Обучать модель для YOLO
			</label>
			<p
				style={{ fontSize: 13, color: "#666", marginTop: 8, marginBottom: 12 }}
			>
				Если включено, отдельно учится модель на вырезках с людьми. Она
				используется, когда включена детекция объектов YOLO.
			</p>
			<TextField
				label="Папка с тренировочными вырезками"
				value={yoloTrainDir}
				size="small"
				fullWidth
				disabled={running || !trainYoloModel}
				onChange={(event) => setYoloTrainDir(event.target.value)}
				sx={{ marginBottom: "16px" }}
			/>
			<TextField
				label="Папка с валидационными вырезками"
				value={yoloValDir}
				size="small"
				fullWidth
				disabled={running || !trainYoloModel}
				onChange={(event) => setYoloValDir(event.target.value)}
				sx={{ marginBottom: "12px" }}
			/>
			<label style={{ display: "block", marginBottom: 0 }}>
				<input
					type="checkbox"
					checked={prepareYoloCrops}
					disabled={running || !trainYoloModel}
					onChange={(event) => setPrepareYoloCrops(event.target.checked)}
				/>{" "}
				Подготовить вырезки из сцен, если их ещё нет
			</label>
			<p
				style={{ fontSize: 13, color: "#666", marginTop: 8, marginBottom: 20 }}
			>
				Если включено, YOLO вырежет людей из клипов полной сцены в папки вырезок
				перед обучением.
			</p>

			<label style={{ display: "block", marginBottom: 12 }}>
				<input
					type="checkbox"
					checked={savePlots}
					disabled={running}
					onChange={(event) => setSavePlots(event.target.checked)}
				/>{" "}
				Сохранять графики обучения
			</label>
			<TextField
				label="Путь сохранения графиков"
				value={plotDir}
				size="small"
				fullWidth
				disabled={!savePlots || running}
				onChange={(event) => setPlotDir(event.target.value)}
				sx={{ marginBottom: "20px" }}
			/>

			<h3 style={{ marginBottom: 8 }}>Классы действий</h3>
			{scanLoading && (
				<div style={{ fontSize: 13, marginBottom: 8 }}>
					Чтение папок выборок...
				</div>
			)}
			{scanError && (
				<div style={{ color: "#dc2626", marginBottom: 12 }}>{scanError}</div>
			)}
			{!scanLoading && classes.length === 0 && !scanError && (
				<div style={{ fontSize: 13, color: "#666", marginBottom: 12 }}>
					В тренировочной папке нет классов.
				</div>
			)}
			{classes.map((item) => (
				<div
					key={item.key}
					style={{
						marginBottom: 12,
						padding: 10,
						border: "1px solid #ddd",
						borderRadius: 6,
					}}
				>
					<TextField
						label={`Название класса (${item.key})`}
						value={item.label}
						size="small"
						fullWidth
						disabled={running}
						onChange={(event) => updateClassLabel(item.key, event.target.value)}
					/>
					<div style={{ fontSize: 13, opacity: 0.75, marginTop: 8 }}>
						Сцены: {item.train_videos} train / {item.val_videos} val.
						YOLO-вырезки: {item.yolo_train_videos} train /{" "}
						{item.yolo_val_videos} val
						{item.missing_flow_train +
							item.missing_flow_val +
							item.missing_flow_yolo_train +
							item.missing_flow_yolo_val >
						0
							? `. Будет подготовлен оптический поток для ${
									item.missing_flow_train +
									item.missing_flow_val +
									item.missing_flow_yolo_train +
									item.missing_flow_yolo_val
							  } файлов`
							: ""}
					</div>
					{trainSceneModel && !item.has_val && (
						<div style={{ color: "#dc2626", marginTop: 8, fontSize: 13 }}>
							В валидационной выборке сцен нет папки «{item.key}»
						</div>
					)}
					{trainYoloModel && !prepareYoloCrops && !item.has_yolo_val && (
						<div style={{ color: "#dc2626", marginTop: 8, fontSize: 13 }}>
							В валидационной выборке YOLO-вырезок нет папки «{item.key}»
						</div>
					)}
				</div>
			))}
			{missingValClasses.length > 0 && (
				<div style={{ color: "#dc2626", marginBottom: 8, fontSize: 13 }}>
					Для {missingValClasses.length}{" "}
					{missingValClasses.length === 1 ? "класса" : "классов"} из train сцен
					нет соответствующей папки в val.
				</div>
			)}
			{missingYoloValClasses.length > 0 && (
				<div style={{ color: "#dc2626", marginBottom: 16, fontSize: 13 }}>
					Для {missingYoloValClasses.length}{" "}
					{missingYoloValClasses.length === 1 ? "класса" : "классов"} из train
					YOLO-вырезок нет соответствующей папки в val.
				</div>
			)}

			<Accordion
				disableGutters
				elevation={0}
				sx={{
					border: "1px solid #ddd",
					borderRadius: "6px !important",
					marginBottom: "20px",
					"&:before": { display: "none" },
				}}
			>
				<AccordionSummary expandIcon={<ExpandMoreIcon />}>
					Расширенные параметры
				</AccordionSummary>
				<AccordionDetails>
					<TextField
						label="Количество эпох"
						type="number"
						size="small"
						fullWidth
						disabled={running}
						value={epochs}
						onChange={(event) => setEpochs(Number(event.target.value))}
						slotProps={{ htmlInput: { min: 1, max: 500 } }}
						sx={{ marginBottom: "12px" }}
					/>
					<TextField
						label="Скорость обучения сетей признаков"
						size="small"
						fullWidth
						disabled={running}
						value={backboneLr}
						onChange={(event) => setBackboneLr(event.target.value)}
						sx={{ marginBottom: "12px" }}
					/>
					<TextField
						label="Скорость обучения классификатора"
						size="small"
						fullWidth
						disabled={running}
						value={headLr}
						onChange={(event) => setHeadLr(event.target.value)}
						sx={{ marginBottom: "12px" }}
					/>
					<TextField
						label="Размер батча"
						type="number"
						size="small"
						fullWidth
						disabled={running}
						value={batchSize}
						onChange={(event) => setBatchSize(Number(event.target.value))}
						slotProps={{ htmlInput: { min: 1, max: 64 } }}
						sx={{ marginBottom: "12px" }}
					/>
					<TextField
						label="Регуляризация (weight decay)"
						size="small"
						fullWidth
						disabled={running}
						value={weightDecay}
						onChange={(event) => setWeightDecay(event.target.value)}
						sx={{ marginBottom: "12px" }}
					/>
					<TextField
						label="Dropout"
						size="small"
						fullWidth
						disabled={running}
						value={dropout}
						onChange={(event) => setDropout(event.target.value)}
						sx={{ marginBottom: "12px" }}
					/>
					<TextField
						label="Сглаживание меток"
						size="small"
						fullWidth
						disabled={running}
						value={labelSmoothing}
						onChange={(event) => setLabelSmoothing(event.target.value)}
						sx={{ marginBottom: "12px" }}
					/>
					<TextField
						label="Ранняя остановка"
						type="number"
						size="small"
						fullWidth
						disabled={running}
						value={patience}
						onChange={(event) => setPatience(Number(event.target.value))}
						slotProps={{ htmlInput: { min: 0, max: 50 } }}
						sx={{ marginBottom: "12px" }}
					/>
					<TextField
						label="Объединение RGB и оптического потока"
						select
						size="small"
						fullWidth
						disabled={running}
						value={fusion}
						onChange={(event) => setFusion(event.target.value)}
						sx={{ marginBottom: "12px" }}
					>
						<MenuItem value="add">Сложение (add)</MenuItem>
						<MenuItem value="concat">Конкатенация (concat)</MenuItem>
					</TextField>
					<label style={{ display: "block", marginBottom: 0 }}>
						<input
							type="checkbox"
							checked={useClassWeights}
							disabled={running}
							onChange={(event) => setUseClassWeights(event.target.checked)}
						/>{" "}
						Использовать веса классов
					</label>
					<p style={{ fontSize: 13, color: "#666", marginTop: 8 }}>
						Если включено, редкие классы получают больший вес в функции потерь,
						чтобы модель лучше училась распознавать малочисленные действия.
					</p>
				</AccordionDetails>
			</Accordion>

			{status && status.state !== "idle" && (
				<div
					style={{
						marginBottom: 16,
						padding: 12,
						border: "1px solid #ddd",
						borderRadius: 6,
					}}
				>
					<div style={{ marginBottom: 8 }}>{status.message || "Обучение"}</div>
					<LinearProgress
						variant={status.total > 0 ? "determinate" : "indeterminate"}
						value={progressValue(status)}
					/>
					{status.stage === "train" && status.epoch > 0 && (
						<div style={{ fontSize: 13, marginTop: 8, opacity: 0.8 }}>
							Эпоха {status.epoch} из {status.epochs || defaults.epochs}. Loss:{" "}
							{formatMetric(status.train_loss)}, val loss:{" "}
							{formatMetric(status.val_loss)}, F1: {formatMetric(status.val_f1)}
						</div>
					)}
					{status.state === "completed" && (
						<div style={{ marginTop: 8, color: "#15803d" }}>
							Обучение завершено. Новая модель сохранена и загружена.
						</div>
					)}
					{status.state === "cancelled" && (
						<div style={{ marginTop: 8, color: "#b45309" }}>
							Обучение отменено.
						</div>
					)}
					{status.state === "error" && (
						<div style={{ marginTop: 8, color: "#dc2626" }}>
							{status.error || "Ошибка обучения"}
						</div>
					)}
				</div>
			)}

			{running ? (
				<button
					onClick={cancelTraining}
					style={{
						padding: "8px 16px",
						backgroundColor: "#dc2626",
						color: "white",
						border: "none",
						borderRadius: 4,
						cursor: "pointer",
						marginTop: 20,
					}}
				>
					Отменить
				</button>
			) : (
				<button
					onClick={startTraining}
					disabled={!canStart}
					style={{
						padding: "8px 16px",
						backgroundColor: canStart ? "#007bff" : "#94a3b8",
						color: "white",
						border: "none",
						borderRadius: 4,
						cursor: canStart ? "pointer" : "not-allowed",
						marginTop: 20,
					}}
				>
					Начать обучение
				</button>
			)}

			{actionError && (
				<div style={{ marginTop: 10, color: "#dc2626" }}>{actionError}</div>
			)}
		</div>
	);
};
