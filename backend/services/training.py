from __future__ import annotations

import asyncio
import copy
import gc
import importlib.util
import os
import shutil
import sys
import threading
import traceback
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified

from core.config import (
    ANOMALY_MODEL_PATH,
    ANOMALY_YOLO_MODEL_PATH,
    DEFAULT_SETTINGS,
    FRONTEND_LABELS,
)
from core.db import AsyncSessionLocal
from models.settings import Settings
from schemas.training import (
    DatasetClassResponse,
    DatasetScanResponse,
    TrainingDefaults,
    TrainingStartRequest,
    TrainingStatusResponse,
)
from services.dataset_scan import scan_dataset_classes, split_has_videos
from services.settings import get_settings, load_settings
from utils.optical_flow_cache import precompute_missing_flow
from utils.training_runtime import TrainingCancelled, raise_if_cancelled

BACKEND_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TRAIN_DIR = BACKEND_ROOT / "dataset" / "train"
DEFAULT_VAL_DIR = BACKEND_ROOT / "dataset" / "val"
DEFAULT_YOLO_TRAIN_DIR = BACKEND_ROOT / "dataset-cropped" / "train"
DEFAULT_YOLO_VAL_DIR = BACKEND_ROOT / "dataset-cropped" / "val"
DEFAULT_PLOT_DIR = BACKEND_ROOT / "fine-tune" / "training_plots"
LAST_CHECKPOINT_NAME = "suspicious_actions.pth"
LAST_YOLO_CHECKPOINT_NAME = "suspicious_actions_yolo.pth"

DEFAULT_HYPERPARAMS = TrainingDefaults(
    train_dir=str(DEFAULT_TRAIN_DIR),
    val_dir=str(DEFAULT_VAL_DIR),
    yolo_train_dir=str(DEFAULT_YOLO_TRAIN_DIR),
    yolo_val_dir=str(DEFAULT_YOLO_VAL_DIR),
    train_scene_model=True,
    train_yolo_model=True,
    prepare_yolo_crops=True,
    plot_dir=str(DEFAULT_PLOT_DIR),
    epochs=40,
    backbone_lr=1e-5,
    head_lr=1e-4,
    batch_size=4,
    weight_decay=5e-3,
    dropout=0.65,
    label_smoothing=0.1,
    patience=3,
    fusion="add",
    use_class_weights=True,
)

RUNNING_STATES = {"precomputing", "cropping", "training"}
_crop_module = None

_lock = threading.Lock()
_cancel_event = threading.Event()
_worker: Optional[threading.Thread] = None
_training_module = None
_state: Dict[str, Any] = {
    "state": "idle",
    "stage": None,
    "message": "",
    "current": 0,
    "total": 0,
    "epoch": 0,
    "epochs": 0,
    "batch": 0,
    "batches": 0,
    "train_loss": None,
    "val_loss": None,
    "val_acc": None,
    "val_f1": None,
    "history": {},
    "error": None,
    "started_at": None,
    "finished_at": None,
}


def resolve_user_path(path: str) -> Path:
    raw = Path(str(path).strip().strip('"'))
    if not raw.is_absolute():
        raw = BACKEND_ROOT / raw
    return Path(os.path.normpath(str(raw)))


def class_label_map() -> Dict[str, str]:
    settings = get_settings() or {}
    stored = dict(settings.get("actionLabels") or {})
    merged = dict(FRONTEND_LABELS)
    merged.update({key: value for key, value in stored.items() if value})
    return merged


def scan_classes(
    train_dir: str,
    val_dir: str,
    yolo_train_dir: str = "",
    yolo_val_dir: str = "",
) -> DatasetScanResponse:
    train_path = resolve_user_path(train_dir) if train_dir.strip() else Path()
    val_path = resolve_user_path(val_dir) if val_dir.strip() else Path()
    yolo_train_path = (
        resolve_user_path(yolo_train_dir) if yolo_train_dir.strip() else Path()
    )
    yolo_val_path = resolve_user_path(yolo_val_dir) if yolo_val_dir.strip() else Path()
    train_exists = bool(train_dir.strip()) and train_path.is_dir()
    val_exists = bool(val_dir.strip()) and val_path.is_dir()
    yolo_train_exists = bool(yolo_train_dir.strip()) and yolo_train_path.is_dir()
    yolo_val_exists = bool(yolo_val_dir.strip()) and yolo_val_path.is_dir()
    error = None
    if not train_exists and not yolo_train_exists:
        error = "Папка тренировочной выборки не найдена"

    classes = []
    if train_exists or yolo_train_exists:
        classes = [
            DatasetClassResponse(
                key=item.key,
                label=item.label,
                train_videos=item.train_videos,
                val_videos=item.val_videos,
                has_val=item.has_val,
                missing_flow_train=item.missing_flow_train,
                missing_flow_val=item.missing_flow_val,
                yolo_train_videos=item.yolo_train_videos,
                yolo_val_videos=item.yolo_val_videos,
                has_yolo_train=item.has_yolo_train,
                has_yolo_val=item.has_yolo_val,
                missing_flow_yolo_train=item.missing_flow_yolo_train,
                missing_flow_yolo_val=item.missing_flow_yolo_val,
            )
            for item in scan_dataset_classes(
                str(train_path) if train_exists else "",
                str(val_path) if val_exists else "",
                labels=class_label_map(),
                yolo_train_dir=str(yolo_train_path) if yolo_train_exists else "",
                yolo_val_dir=str(yolo_val_path) if yolo_val_exists else "",
            )
        ]
    return DatasetScanResponse(
        classes=classes,
        train_exists=train_exists,
        val_exists=val_exists,
        yolo_train_exists=yolo_train_exists,
        yolo_val_exists=yolo_val_exists,
        error=error,
    )


def _snapshot() -> Dict[str, Any]:
    with _lock:
        data = copy.deepcopy(_state)
    data["can_cancel"] = data["state"] in RUNNING_STATES
    data["defaults"] = DEFAULT_HYPERPARAMS
    return data


def get_status() -> TrainingStatusResponse:
    return TrainingStatusResponse(**_snapshot())


def _update(**kwargs) -> None:
    with _lock:
        for key, value in kwargs.items():
            _state[key] = value


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_script_module(filename: str, module_name: str):
    existing = sys.modules.get(module_name)
    if existing is not None:
        return existing
    path = BACKEND_ROOT / "fine-tune" / filename
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Не удалось загрузить {filename}")
    module = importlib.util.module_from_spec(spec)
    # Dataclasses and relative imports need the module in sys.modules
    # before exec_module; otherwise they fail with
    # "'NoneType' object has no attribute '__dict__'".
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(module_name, None)
        raise
    return module


def _load_training_module():
    global _training_module
    if _training_module is None:
        _training_module = _load_script_module(
            "anomaly_detection_model.py", "anomaly_detection_model_train"
        )
    return _training_module


def _load_crop_module():
    global _crop_module
    if _crop_module is None:
        _crop_module = _load_script_module(
            "crop_dataset_with_yolo.py", "crop_dataset_with_yolo_train"
        )
    return _crop_module


def _progress_callback(update: Dict[str, Any]) -> None:
    mapped = {}
    for key in (
        "stage",
        "message",
        "current",
        "total",
        "epoch",
        "epochs",
        "batch",
        "batches",
        "train_loss",
        "val_loss",
        "val_acc",
        "val_f1",
        "history",
    ):
        if key in update:
            mapped[key] = update[key]
    if mapped:
        _update(**mapped)


def _cleanup_paths(paths: List[Path]) -> None:
    for path in paths:
        try:
            if path.is_file():
                path.unlink()
        except OSError:
            pass


async def persist_action_labels(
    class_items: List[tuple[str, str]],
    user_id: Optional[str],
    add_detection: bool,
) -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Settings).where(Settings.name == "default"))
        settings = result.scalars().first()
        stored = dict((settings.settings if settings else DEFAULT_SETTINGS) or {})
        detection = dict(stored.get("detection") or {})
        labels = dict(stored.get("actionLabels") or {})
        for key, label in class_items:
            if label:
                labels[key] = label
            if add_detection and key != "normal" and key not in detection:
                detection[key] = {
                    "enabled": True,
                    "sensitivity": 0.5,
                    "alert_sensitivity": 0.35,
                }
        stored["detection"] = detection
        stored["actionLabels"] = labels
        stored.setdefault("useObjectDetection", True)
        if settings:
            settings.settings = stored
            if user_id:
                settings.updated_by = str(user_id)
            flag_modified(settings, "settings")
        else:
            settings = Settings(
                name="default",
                settings=stored,
                updated_by=str(user_id) if user_id else None,
            )
            db.add(settings)
        await db.commit()
        await load_settings(db)


def _persist_action_labels_sync(
    class_items: List[tuple[str, str]],
    user_id: Optional[str],
    add_detection: bool,
) -> None:
    asyncio.run(persist_action_labels(class_items, user_id, add_detection))


def _reload_inference_model(checkpoint_path: str, target: str = "scene") -> None:
    from models.anomaly_model import reload_from_checkpoint

    reload_from_checkpoint(checkpoint_path, target=target)


def _promote_checkpoint(temp_best: Path, temp_last: Path, final_best: Path, final_last: Path) -> None:
    if not temp_best.is_file():
        raise RuntimeError("Обучение завершилось без сохранённой модели")
    shutil.copyfile(temp_best, final_best)
    if temp_last.is_file():
        shutil.copyfile(temp_last, final_last)


def _train_one_model(
    payload: TrainingStartRequest,
    names: List[str],
    train_dir: Path,
    val_dir: Path,
    temp_best: Path,
    temp_last: Path,
    plot_prefix: str,
    label: str,
) -> dict:
    plot_dir = (
        resolve_user_path(payload.plot_dir)
        if payload.save_plots and payload.plot_dir
        else DEFAULT_PLOT_DIR
    )
    _update(
        state="precomputing",
        stage="precompute",
        message=f"{label}: проверка оптического потока...",
        error=None,
        current=0,
        total=0,
    )
    raise_if_cancelled(_cancel_event)
    precompute_missing_flow(
        [str(train_dir), str(val_dir)],
        skip_existing=True,
        cancel_event=_cancel_event,
        progress_callback=_progress_callback,
        show_progress_bar=False,
    )

    raise_if_cancelled(_cancel_event)
    _update(
        state="training",
        stage="train",
        message=f"{label}: загрузка модели и данных...",
        current=0,
        total=payload.epochs,
        epoch=0,
        epochs=payload.epochs,
    )
    module = _load_training_module()
    history = module.train_model(
        fusion=payload.fusion if payload.fusion in {"add", "concat"} else "add",
        plot_metrics=payload.save_plots,
        online_flow=False,
        num_epochs=payload.epochs,
        early_stop_patience=payload.patience,
        weight_decay_val=payload.weight_decay,
        dropout=payload.dropout,
        label_smooth=payload.label_smoothing,
        backbone_learning_rate=payload.backbone_lr,
        head_learning_rate=payload.head_lr,
        class_weights=payload.use_class_weights,
        train_root=str(train_dir),
        val_root=str(val_dir),
        names=names,
        plot_dir=str(plot_dir) if payload.save_plots else None,
        checkpoint_path=str(temp_last),
        best_checkpoint_path=str(temp_best),
        batch_size_val=payload.batch_size,
        cancel_event=_cancel_event,
        progress_callback=_progress_callback,
        dataloader_workers=0,
        plot_prefix=plot_prefix,
    )
    gc.collect()
    try:
        import torch

        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:
        pass
    return history or {}


def _prepare_yolo_crops(scene_dir: Path, yolo_dir: Path, label: str) -> None:
    yolo_dir.mkdir(parents=True, exist_ok=True)
    _update(
        state="cropping",
        stage="crop",
        message=f"{label}: вырезание людей через YOLO...",
        current=0,
        total=0,
    )
    crop_module = _load_crop_module()
    crop_module.crop_person_dataset(
        scene_dir,
        yolo_dir,
        cancel_event=_cancel_event,
        progress_callback=_progress_callback,
    )


def _run_job(
    payload: TrainingStartRequest,
    class_items: List[tuple[str, str]],
    _user_id: Optional[str],
    temp_paths: List[Path],
) -> None:
    names = [key for key, _label in class_items]
    histories: Dict[str, Any] = {}
    completed_parts: List[str] = []

    try:
        if payload.train_scene_model:
            scene_best, scene_last = temp_paths[0], temp_paths[1]
            history = _train_one_model(
                payload,
                names,
                resolve_user_path(payload.train_dir),
                resolve_user_path(payload.val_dir),
                scene_best,
                scene_last,
                "train_scene",
                "Модель полной сцены",
            )
            raise_if_cancelled(_cancel_event)
            _promote_checkpoint(
                scene_best,
                scene_last,
                BACKEND_ROOT / ANOMALY_MODEL_PATH,
                BACKEND_ROOT / LAST_CHECKPOINT_NAME,
            )
            try:
                _reload_inference_model(
                    str(BACKEND_ROOT / ANOMALY_MODEL_PATH), target="scene"
                )
            except Exception as exc:
                print(f"Failed to reload scene model after training: {exc}")
            histories["scene"] = history
            completed_parts.append("полной сцены")

        if payload.train_yolo_model:
            yolo_train = resolve_user_path(
                payload.yolo_train_dir or str(DEFAULT_YOLO_TRAIN_DIR)
            )
            yolo_val = resolve_user_path(
                payload.yolo_val_dir or str(DEFAULT_YOLO_VAL_DIR)
            )
            if payload.prepare_yolo_crops:
                scene_train = resolve_user_path(payload.train_dir)
                scene_val = resolve_user_path(payload.val_dir)
                if not split_has_videos(str(yolo_train)):
                    _prepare_yolo_crops(scene_train, yolo_train, "Train YOLO")
                if not split_has_videos(str(yolo_val)):
                    _prepare_yolo_crops(scene_val, yolo_val, "Val YOLO")
            if not split_has_videos(str(yolo_train)):
                raise RuntimeError("После подготовки в выборке YOLO-вырезок нет видео")

            yolo_offset = 2 if payload.train_scene_model else 0
            yolo_best, yolo_last = temp_paths[yolo_offset], temp_paths[yolo_offset + 1]
            history = _train_one_model(
                payload,
                names,
                yolo_train,
                yolo_val,
                yolo_best,
                yolo_last,
                "train_yolo",
                "Модель YOLO-вырезок",
            )
            raise_if_cancelled(_cancel_event)
            _promote_checkpoint(
                yolo_best,
                yolo_last,
                BACKEND_ROOT / ANOMALY_YOLO_MODEL_PATH,
                BACKEND_ROOT / LAST_YOLO_CHECKPOINT_NAME,
            )
            try:
                _reload_inference_model(
                    str(BACKEND_ROOT / ANOMALY_YOLO_MODEL_PATH), target="yolo"
                )
            except Exception as exc:
                print(f"Failed to reload YOLO crop model after training: {exc}")
            histories["yolo"] = history
            completed_parts.append("Модель для YOLO")

        message = "Обучение завершено"
        if completed_parts:
            message = "Обучение завершено: " + " и ".join(completed_parts)
        _update(
            state="completed",
            stage="train",
            message=message,
            history=histories.get("yolo") or histories.get("scene") or {},
            finished_at=_now(),
            current=payload.epochs,
            total=payload.epochs,
        )
    except TrainingCancelled:
        _update(
            state="cancelled",
            message="Обучение отменено",
            finished_at=_now(),
        )
    except Exception as exc:
        if _cancel_event.is_set():
            _update(
                state="cancelled",
                message="Обучение отменено",
                finished_at=_now(),
            )
        else:
            traceback.print_exc()
            _update(
                state="error",
                message="Ошибка обучения",
                error=str(exc),
                finished_at=_now(),
            )
    finally:
        _cleanup_paths(temp_paths)


def start_training(payload: TrainingStartRequest, user_id: Optional[str]) -> TrainingStatusResponse:
    global _worker

    if not payload.train_scene_model and not payload.train_yolo_model:
        raise ValueError("Выберите хотя бы одну модель: полная сцена или YOLO-вырезки")
    if payload.save_plots and not (payload.plot_dir and payload.plot_dir.strip()):
        raise ValueError("Укажите путь сохранения графиков")
    if payload.fusion not in {"add", "concat"}:
        raise ValueError("fusion должен быть add или concat")

    train_dir = resolve_user_path(payload.train_dir)
    val_dir = resolve_user_path(payload.val_dir)
    yolo_train_dir = resolve_user_path(
        payload.yolo_train_dir or str(DEFAULT_YOLO_TRAIN_DIR)
    )
    yolo_val_dir = resolve_user_path(payload.yolo_val_dir or str(DEFAULT_YOLO_VAL_DIR))

    yolo_train_ready = split_has_videos(str(yolo_train_dir))
    need_scene_source = payload.train_scene_model or (
        payload.train_yolo_model
        and payload.prepare_yolo_crops
        and not yolo_train_ready
    )
    if need_scene_source:
        if not train_dir.is_dir():
            raise ValueError("Папка тренировочной выборки полной сцены не найдена")
        if not val_dir.is_dir():
            raise ValueError("Папка валидационной выборки полной сцены не найдена")

    class_items: List[tuple[str, str]] = []
    seen = set()
    for item in payload.classes:
        key = item.key.strip()
        if not key or key in seen:
            continue
        seen.add(key)
        class_items.append((key, (item.label or "").strip() or key))
    if not class_items:
        raise ValueError("Не найдены классы действий в тренировочной выборке")

    scan = scan_dataset_classes(
        str(train_dir) if train_dir.is_dir() else "",
        str(val_dir) if val_dir.is_dir() else "",
        labels={},
        yolo_train_dir=str(yolo_train_dir) if yolo_train_dir.is_dir() else "",
        yolo_val_dir=str(yolo_val_dir) if yolo_val_dir.is_dir() else "",
    )
    if payload.train_scene_model:
        train_counts = {item.key: item.train_videos for item in scan}
        if not any(train_counts.get(key, 0) > 0 for key, _label in class_items):
            raise ValueError("В тренировочной выборке полной сцены нет видеофайлов")
    if payload.train_yolo_model and not payload.prepare_yolo_crops:
        yolo_counts = {item.key: item.yolo_train_videos for item in scan}
        if not any(yolo_counts.get(key, 0) > 0 for key, _label in class_items):
            raise ValueError("В выборке YOLO-вырезок нет видеофайлов")

    with _lock:
        if _state["state"] in RUNNING_STATES:
            raise RuntimeError("Обучение уже выполняется")
        _cancel_event.clear()
        run_id = uuid.uuid4().hex[:8]
        temp_paths: List[Path] = []
        if payload.train_scene_model:
            temp_paths.extend(
                [
                    BACKEND_ROOT / f"suspicious_actions_best.training-{run_id}.pth",
                    BACKEND_ROOT / f"suspicious_actions.training-{run_id}.pth",
                ]
            )
        if payload.train_yolo_model:
            temp_paths.extend(
                [
                    BACKEND_ROOT / f"suspicious_actions_yolo_best.training-{run_id}.pth",
                    BACKEND_ROOT / f"suspicious_actions_yolo.training-{run_id}.pth",
                ]
            )
        _state.update(
            {
                "state": "precomputing",
                "stage": "precompute",
                "message": "Запуск обучения...",
                "current": 0,
                "total": 0,
                "epoch": 0,
                "epochs": payload.epochs,
                "batch": 0,
                "batches": 0,
                "train_loss": None,
                "val_loss": None,
                "val_acc": None,
                "val_f1": None,
                "history": {},
                "error": None,
                "started_at": _now(),
                "finished_at": None,
            }
        )
        _worker = threading.Thread(
            target=_run_job,
            args=(payload, class_items, user_id, temp_paths),
            daemon=True,
            name="model-training",
        )
        worker = _worker

    try:
        asyncio.get_running_loop().create_task(
            persist_action_labels(class_items, user_id, add_detection=True)
        )
    except RuntimeError:
        _persist_action_labels_sync(class_items, user_id, add_detection=True)

    worker.start()
    return get_status()


def cancel_training() -> TrainingStatusResponse:
    with _lock:
        if _state["state"] not in RUNNING_STATES:
            raise RuntimeError("Сейчас обучение не выполняется")
        _cancel_event.set()
        _state["message"] = "Отмена обучения..."
    return get_status()


def reset_training_state_for_tests() -> None:
    global _worker
    with _lock:
        _cancel_event.set()
        _worker = None
        _state.update(
            {
                "state": "idle",
                "stage": None,
                "message": "",
                "current": 0,
                "total": 0,
                "epoch": 0,
                "epochs": 0,
                "batch": 0,
                "batches": 0,
                "train_loss": None,
                "val_loss": None,
                "val_acc": None,
                "val_f1": None,
                "history": {},
                "error": None,
                "started_at": None,
                "finished_at": None,
            }
        )
    _cancel_event.clear()
