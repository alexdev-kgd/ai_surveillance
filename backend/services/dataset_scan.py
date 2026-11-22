from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict, List, Optional

from utils.optical_flow_cache import FLOW_SUFFIX, is_video_filename, list_class_folders


@dataclass
class DatasetClassInfo:
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


def count_videos(class_dir: str) -> tuple[int, int]:
    """Return (video_count, missing_flow_count)."""
    if not os.path.isdir(class_dir):
        return 0, 0
    videos = 0
    missing = 0
    for name in os.listdir(class_dir):
        if not is_video_filename(name):
            continue
        videos += 1
        stem, _ = os.path.splitext(os.path.join(class_dir, name))
        if not os.path.exists(stem + FLOW_SUFFIX):
            missing += 1
    return videos, missing


def split_has_videos(root: str) -> bool:
    if not root or not os.path.isdir(root):
        return False
    for key in list_class_folders(root):
        videos, _missing = count_videos(os.path.join(root, key))
        if videos > 0:
            return True
    return False


def scan_dataset_classes(
    train_dir: str,
    val_dir: str,
    labels: Optional[Dict[str, str]] = None,
    yolo_train_dir: str = "",
    yolo_val_dir: str = "",
) -> List[DatasetClassInfo]:
    labels = labels or {}
    scene_classes = list_class_folders(train_dir)
    yolo_classes = list_class_folders(yolo_train_dir)
    keys = list(dict.fromkeys([*scene_classes, *yolo_classes]))
    val_classes = set(list_class_folders(val_dir))
    yolo_val_classes = set(list_class_folders(yolo_val_dir))
    yolo_train_classes = set(yolo_classes)
    result: List[DatasetClassInfo] = []
    for key in keys:
        train_videos, missing_train = count_videos(os.path.join(train_dir, key))
        has_val = key in val_classes
        val_videos, missing_val = (
            count_videos(os.path.join(val_dir, key)) if has_val else (0, 0)
        )
        has_yolo_train = key in yolo_train_classes
        yolo_train_videos, missing_yolo_train = (
            count_videos(os.path.join(yolo_train_dir, key)) if has_yolo_train else (0, 0)
        )
        has_yolo_val = key in yolo_val_classes
        yolo_val_videos, missing_yolo_val = (
            count_videos(os.path.join(yolo_val_dir, key)) if has_yolo_val else (0, 0)
        )
        result.append(
            DatasetClassInfo(
                key=key,
                label=labels.get(key) or key,
                train_videos=train_videos,
                val_videos=val_videos,
                has_val=has_val,
                missing_flow_train=missing_train,
                missing_flow_val=missing_val,
                yolo_train_videos=yolo_train_videos,
                yolo_val_videos=yolo_val_videos,
                has_yolo_train=has_yolo_train,
                has_yolo_val=has_yolo_val,
                missing_flow_yolo_train=missing_yolo_train,
                missing_flow_yolo_val=missing_yolo_val,
            )
        )
    return result
