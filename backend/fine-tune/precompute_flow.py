import os
import cv2
import numpy as np
from tqdm import tqdm

# === CONFIG ===
DATASET_ROOT = "../dataset"
FLOW_SUFFIX = "_flow.npy"

FLOW_PARAMS = dict(
    pyr_scale=0.5,
    levels=3,
    winsize=15,
    iterations=3,
    poly_n=5,
    poly_sigma=1.2,
    flags=0,
)


def compute_flow(video_path, clip_len=50, size=(224, 224)):
    cap = cv2.VideoCapture(video_path, cv2.CAP_FFMPEG)

    frames = []

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        frame = cv2.resize(frame, size)
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        frames.append(gray)

    cap.release()

    if len(frames) < 2:
        return None

    # === СЭМПЛИНГ ===
    indices = np.linspace(0, len(frames) - 1, clip_len).astype(int)
    frames = [frames[i] for i in indices]

    flows = []

    for prev, curr in zip(frames[:-1], frames[1:]):
        flow = cv2.calcOpticalFlowFarneback(
            prev,
            curr,
            None,
            **FLOW_PARAMS
        )
        flows.append(flow.astype(np.float32))

    flow = np.array(flows)  # (clip_len-1, H, W, 2)

    # === НОРМАЛИЗАЦИЯ ===
    max_val = np.abs(flow).max()
    if max_val > 0:
        flow = np.clip(flow / max_val, -1, 1)

    return flow.astype(np.float16)


def process_dataset(root):
    total_videos = 0
    processed = 0

    for split in ["train", "val"]:
        split_dir = os.path.join(root, split)

        for cls in os.listdir(split_dir):
            cls_dir = os.path.join(split_dir, cls)

            if not os.path.isdir(cls_dir):
                continue

            videos = [
                f for f in os.listdir(cls_dir)
                if f.lower().endswith((".mp4", ".avi", ".mov", ".mkv"))
            ]

            for video_file in tqdm(videos, desc=f"{split}/{cls}"):
                total_videos += 1

                video_path = os.path.join(cls_dir, video_file)
                stem, _ = os.path.splitext(video_path)
                flow_path = stem + FLOW_SUFFIX

                # skip if already exists
                # if os.path.exists(flow_path):
                #     continue

                flow = compute_flow(video_path)

                if flow is None:
                    print(f"[WARN] Skipping {video_path} (too short)")
                    continue

                np.save(flow_path, flow)
                processed += 1

    print(f"\nDone!")
    print(f"Total videos: {total_videos}")
    print(f"Processed: {processed}")


if __name__ == "__main__":
    process_dataset(DATASET_ROOT)