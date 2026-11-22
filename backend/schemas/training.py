from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class TrainingClassLabel(BaseModel):
    key: str = Field(min_length=1)
    label: str = ""


class TrainingStartRequest(BaseModel):
    train_dir: str = Field(min_length=1)
    val_dir: str = Field(min_length=1)
    yolo_train_dir: str = ""
    yolo_val_dir: str = ""
    train_scene_model: bool = True
    train_yolo_model: bool = True
    prepare_yolo_crops: bool = True
    save_plots: bool = False
    plot_dir: Optional[str] = None
    classes: List[TrainingClassLabel]
    epochs: int = Field(default=40, ge=1, le=500)
    backbone_lr: float = Field(default=1e-5, gt=0, le=1)
    head_lr: float = Field(default=1e-4, gt=0, le=1)
    batch_size: int = Field(default=4, ge=1, le=64)
    weight_decay: float = Field(default=5e-3, ge=0, le=1)
    dropout: float = Field(default=0.65, ge=0, le=0.95)
    label_smoothing: float = Field(default=0.1, ge=0, le=0.5)
    patience: int = Field(default=3, ge=0, le=50)
    fusion: Literal["add", "concat"] = "add"
    use_class_weights: bool = True


class DatasetClassResponse(BaseModel):
    key: str
    label: str
    train_videos: int
    val_videos: int
    has_val: bool
    missing_flow_train: int
    missing_flow_val: int
    yolo_train_videos: int = 0
    yolo_val_videos: int = 0
    has_yolo_train: bool = False
    has_yolo_val: bool = False
    missing_flow_yolo_train: int = 0
    missing_flow_yolo_val: int = 0


class DatasetScanResponse(BaseModel):
    classes: List[DatasetClassResponse]
    train_exists: bool
    val_exists: bool
    yolo_train_exists: bool = False
    yolo_val_exists: bool = False
    error: Optional[str] = None


class TrainingDefaults(BaseModel):
    train_dir: str
    val_dir: str
    yolo_train_dir: str
    yolo_val_dir: str
    train_scene_model: bool
    train_yolo_model: bool
    prepare_yolo_crops: bool
    plot_dir: str
    epochs: int
    backbone_lr: float
    head_lr: float
    batch_size: int
    weight_decay: float
    dropout: float
    label_smoothing: float
    patience: int
    fusion: str
    use_class_weights: bool


class TrainingStatusResponse(BaseModel):
    state: str
    stage: Optional[str] = None
    message: str = ""
    current: int = 0
    total: int = 0
    epoch: int = 0
    epochs: int = 0
    batch: int = 0
    batches: int = 0
    train_loss: Optional[float] = None
    val_loss: Optional[float] = None
    val_acc: Optional[float] = None
    val_f1: Optional[float] = None
    history: Dict[str, List[float]] = Field(default_factory=dict)
    error: Optional[str] = None
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    can_cancel: bool = False
    defaults: TrainingDefaults
