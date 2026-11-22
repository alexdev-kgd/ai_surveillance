"""Precompute *_flow.npy files for dataset class folders."""
from __future__ import annotations

import os
from typing import Callable, Dict, Iterable, List, Optional, Sequence

import numpy as np
from tqdm import tqdm

from utils.training_runtime import raise_if_cancelled
from utils.video_preprocess import (
    CLIP_LEN,
    FLOW_SUFFIX,
    FRAME_SIZE,
    SAMPLE_STRIDE,
    compute_optical_flow_clip,
    read_video_strided_rgb,
)

VIDEO_EXTENSIONS = (".mp4", ".avi", ".mov", ".mkv")
ProgressCallback = Callable[[Dict], None]


def is_video_filename(name: str) -> bool:
    return name.lower().endswith(VIDEO_EXTENSIONS)


def flow_path_for(video_path: str) -> str:
    stem, _ = os.path.splitext(video_path)
    return stem + FLOW_SUFFIX


def list_class_folders(root: str) -> List[str]:
    if not root or not os.path.isdir(root):
        return []
    names = []
    for entry in os.listdir(root):
        path = os.path.join(root, entry)
        if os.path.isdir(path) and not entry.startswith("."):
            names.append(entry)
    return sorted(names)


def list_videos(class_dir: str) -> List[str]:
    if not os.path.isdir(class_dir):
        return []
    videos = [
        os.path.join(class_dir, name)
        for name in os.listdir(class_dir)
        if is_video_filename(name)
    ]
    videos.sort()
    return videos


def compute_flow_for_video(video_path: str) -> Optional[np.ndarray]:
    frames = read_video_strided_rgb(
        video_path,
        clip_len=CLIP_LEN,
        stride=SAMPLE_STRIDE,
        size=FRAME_SIZE,
    )
    if len(frames) < 2:
        return None
    flow = compute_optical_flow_clip(frames, size=FRAME_SIZE, normalize=True)
    return flow.astype(np.float16)


def collect_videos_for_precompute(
    split_dirs: Sequence[str],
    skip_existing: bool = True,
) -> List[tuple[str, str, str]]:
    """
    Return (split_label, class_name, video_path) for videos that still need flow.
    """
    jobs: List[tuple[str, str, str]] = []
    for split_dir in split_dirs:
        if not split_dir or not os.path.isdir(split_dir):
            continue
        split_label = os.path.basename(os.path.normpath(split_dir))
        for cls in list_class_folders(split_dir):
            for video_path in list_videos(os.path.join(split_dir, cls)):
                if skip_existing and os.path.exists(flow_path_for(video_path)):
                    continue
                jobs.append((split_label, cls, video_path))
    return jobs


def precompute_missing_flow(
    split_dirs: Sequence[str],
    skip_existing: bool = True,
    cancel_event=None,
    progress_callback: Optional[ProgressCallback] = None,
    show_progress_bar: bool = True,
    compute_fn: Callable[[str], Optional[np.ndarray]] = compute_flow_for_video,
) -> Dict[str, int]:
    """
    Write *_flow.npy next to videos that do not already have one.

    `split_dirs` are dataset split roots (each contains class subfolders).
    """
    jobs = collect_videos_for_precompute(split_dirs, skip_existing=skip_existing)
    stats = {
        "queued": len(jobs),
        "processed": 0,
        "skipped_short": 0,
        "failed": 0,
    }

    if progress_callback:
        progress_callback(
            {
                "stage": "precompute",
                "current": 0,
                "total": max(len(jobs), 1) if jobs else 0,
                "message": (
                    "Оптический поток уже подготовлен"
                    if not jobs
                    else f"Подготовка оптического потока: 0 из {len(jobs)}"
                ),
            }
        )

    if not jobs:
        return stats

    iterator: Iterable[tuple[str, str, str]] = jobs
    if show_progress_bar:
        iterator = tqdm(jobs, desc="precompute_flow")

    for index, (split_label, cls, video_path) in enumerate(iterator, start=1):
        raise_if_cancelled(cancel_event)
        rel = f"{split_label}/{cls}/{os.path.basename(video_path)}"
        if progress_callback:
            progress_callback(
                {
                    "stage": "precompute",
                    "current": index - 1,
                    "total": len(jobs),
                    "message": f"Подготовка оптического потока: {rel}",
                }
            )

        try:
            flow = compute_fn(video_path)
        except Exception:
            stats["failed"] += 1
            continue

        if flow is None:
            stats["skipped_short"] += 1
            continue

        np.save(flow_path_for(video_path), flow)
        stats["processed"] += 1

        if progress_callback:
            progress_callback(
                {
                    "stage": "precompute",
                    "current": index,
                    "total": len(jobs),
                    "message": f"Подготовка оптического потока: {index} из {len(jobs)}",
                }
            )

    return stats
