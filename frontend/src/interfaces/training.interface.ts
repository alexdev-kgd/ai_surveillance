export interface ITrainingClass {
	key: string;
	label: string;
	train_videos: number;
	val_videos: number;
	has_val: boolean;
	missing_flow_train: number;
	missing_flow_val: number;
	yolo_train_videos: number;
	yolo_val_videos: number;
	has_yolo_train: boolean;
	has_yolo_val: boolean;
	missing_flow_yolo_train: number;
	missing_flow_yolo_val: number;
}

export interface IDatasetScan {
	classes: ITrainingClass[];
	train_exists: boolean;
	val_exists: boolean;
	yolo_train_exists?: boolean;
	yolo_val_exists?: boolean;
	error?: string | null;
}

export interface ITrainingDefaults {
	train_dir: string;
	val_dir: string;
	yolo_train_dir: string;
	yolo_val_dir: string;
	train_scene_model: boolean;
	train_yolo_model: boolean;
	prepare_yolo_crops: boolean;
	plot_dir: string;
	epochs: number;
	backbone_lr: number;
	head_lr: number;
	batch_size: number;
	weight_decay: number;
	dropout: number;
	label_smoothing: number;
	patience: number;
	fusion: string;
	use_class_weights: boolean;
}

export interface ITrainingStatus {
	state: "idle" | "precomputing" | "cropping" | "training" | "completed" | "cancelled" | "error" | string;
	stage?: string | null;
	message: string;
	current: number;
	total: number;
	epoch: number;
	epochs: number;
	batch: number;
	batches: number;
	train_loss?: number | null;
	val_loss?: number | null;
	val_acc?: number | null;
	val_f1?: number | null;
	history: Record<string, number[]>;
	error?: string | null;
	started_at?: string | null;
	finished_at?: string | null;
	can_cancel: boolean;
	defaults: ITrainingDefaults;
}

export interface ITrainingStartRequest {
	train_dir: string;
	val_dir: string;
	yolo_train_dir: string;
	yolo_val_dir: string;
	train_scene_model: boolean;
	train_yolo_model: boolean;
	prepare_yolo_crops: boolean;
	save_plots: boolean;
	plot_dir?: string | null;
	classes: { key: string; label: string }[];
	epochs: number;
	backbone_lr: number;
	head_lr: number;
	batch_size: number;
	weight_decay: number;
	dropout: number;
	label_smoothing: number;
	patience: number;
	fusion: string;
	use_class_weights: boolean;
}
