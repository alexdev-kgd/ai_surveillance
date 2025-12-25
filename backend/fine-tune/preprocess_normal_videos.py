import os
import cv2
import torch
import numpy as np

SOURCE_DIR = "../dataset/train/normal"
OUTPUT_DIR = "../dataset_cropped/train_full_frame/normal"

CLIP_FPS = 30
CLIP_DURATION = 5
CLIP_FRAMES = CLIP_FPS * CLIP_DURATION
MIN_FRAMES = 20

os.makedirs(OUTPUT_DIR, exist_ok=True)

def save_clip(frames, out_path, fps):
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(out_path, fourcc, fps, (224, 224))
    for f in frames:
        writer.write(f)
    writer.release()
    print(f"✅ Saved: {out_path}")

def process_video(video_path):
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    if fps <= 0: fps = CLIP_FPS

    basename = os.path.splitext(os.path.basename(video_path))[0]
    frame_idx = 0
    clip_idx = 0
    buffer = []

    print(f"Processing {basename}...")

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        frame_idx += 1
        frame = cv2.resize(frame, (224, 224))
        buffer.append(frame)

        # if a clip has enough frames, save it
        if len(buffer) >= CLIP_FRAMES:
            out_path = os.path.join(OUTPUT_DIR, f"{basename}_clip{clip_idx}.mp4")
            save_clip(buffer[:CLIP_FRAMES], out_path, fps)
            clip_idx += 1
            buffer = []  # reset for next clip

    # save leftover frames if long enough
    if len(buffer) >= MIN_FRAMES:
        out_path = os.path.join(OUTPUT_DIR, f"{basename}_clip{clip_idx}_final.mp4")
        save_clip(buffer, out_path, fps)

    cap.release()

if __name__ == "__main__":
    videos = [f for f in os.listdir(SOURCE_DIR) if f.lower().endswith((".mp4", ".avi", ".mov", ".mkv"))]

    for v in videos:
        process_video(os.path.join(SOURCE_DIR, v))

    print("✅ Done! Clips saved in:", OUTPUT_DIR)
