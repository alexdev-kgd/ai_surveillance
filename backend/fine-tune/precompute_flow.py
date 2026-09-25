"""
Precompute optical flow for the dataset using the same sampling as train/serve.

Sampling: sequential frames every SAMPLE_STRIDE until CLIP_LEN RGB frames,
then Farneback between consecutive RGB frames → (CLIP_LEN, H, W, 2) after pad.
"""
import os
import sys

import numpy as np
from tqdm import tqdm

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from utils.video_preprocess import (
    CLIP_LEN,
    FLOW_SUFFIX,
    FRAME_SIZE,
    SAMPLE_STRIDE,
    compute_optical_flow_clip,
    read_video_strided_rgb,
)

DATASET_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "dataset"))


def compute_flow_for_video(video_path: str) -> np.ndarray | None:
    frames = read_video_strided_rgb(
        video_path,
        clip_len=CLIP_LEN,
        stride=SAMPLE_STRIDE,
        size=FRAME_SIZE,
    )
    if len(frames) < 2:
        return None

    # (T, H, W, 2) float32, last flow padded
    flow = compute_optical_flow_clip(frames, size=FRAME_SIZE, normalize=True)
    return flow.astype(np.float16)


def process_dataset(root: str = DATASET_ROOT) -> None:
    total_videos = 0
    processed = 0

    for split in ["train", "val"]:
        split_dir = os.path.join(root, split)
        if not os.path.isdir(split_dir):
            continue

        for cls in os.listdir(split_dir):
            cls_dir = os.path.join(split_dir, cls)
            if not os.path.isdir(cls_dir):
                continue

            videos = [
                f
                for f in os.listdir(cls_dir)
                if f.lower().endswith((".mp4", ".avi", ".mov", ".mkv"))
            ]

            for video_file in tqdm(videos, desc=f"{split}/{cls}"):
                total_videos += 1
                video_path = os.path.join(cls_dir, video_file)
                stem, _ = os.path.splitext(video_path)
                flow_path = stem + FLOW_SUFFIX

                flow = compute_flow_for_video(video_path)
                if flow is None:
                    print(f"[WARN] Skipping {video_path} (too short)")
                    continue

                np.save(flow_path, flow)
                processed += 1

    print("\nDone!")
    print(f"Total videos: {total_videos}")
    print(f"Processed: {processed}")
    print(f"CLIP_LEN={CLIP_LEN}, STRIDE={SAMPLE_STRIDE}, size={FRAME_SIZE}")


if __name__ == "__main__":
    process_dataset(DATASET_ROOT)
