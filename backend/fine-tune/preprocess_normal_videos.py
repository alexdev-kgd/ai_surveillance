import os
import cv2
import torch
import numpy as np
from ultralytics import YOLO
from collections import defaultdict

# -------------------------------
# CONFIGURATION
# -------------------------------
SOURCE_DIR = "../dataset/val/normal"      # Folder with your long normal videos
OUTPUT_DIR = "../dataset_cropped/val/normal"
CLIP_FPS = 30
CLIP_DURATION = 2  # seconds
CLIP_FRAMES = CLIP_FPS * CLIP_DURATION

CONF_THRESHOLD = 0.5  # YOLO person detection confidence
IOU_TRACK_THRESHOLD = 0.4  # how strict for continuing the same track
MIN_FRAMES = 20  # minimum frames required to save a clip

os.makedirs(OUTPUT_DIR, exist_ok=True)

# -------------------------------
# YOLO MODEL (PERSON DETECTION)
# -------------------------------
device = "cuda" if torch.cuda.is_available() else "cpu"
yolo = YOLO("yolov8n.pt").to(device)  # you can use yolov8s.pt for better accuracy

# -------------------------------
# SIMPLE TRACKER (centroid-based)
# -------------------------------
class CentroidTracker:
    def __init__(self, max_distance=100):
        self.next_id = 0
        self.tracks = {}
        self.max_distance = max_distance

    def update(self, detections):
        new_tracks = {}
        used_ids = set()

        for det in detections:
            x1, y1, x2, y2 = det
            cx, cy = (x1 + x2) / 2, (y1 + y2) / 2

            best_id, best_dist = None, float("inf")
            for tid, (tx, ty, _) in self.tracks.items():
                dist = np.hypot(cx - tx, cy - ty)
                if dist < best_dist and dist < self.max_distance:
                    best_id, best_dist = tid, dist

            if best_id is not None:
                used_ids.add(best_id)
                new_tracks[best_id] = (cx, cy, det)
            else:
                new_tracks[self.next_id] = (cx, cy, det)
                self.next_id += 1

        self.tracks = new_tracks
        return {tid: det for tid, (_, _, det) in new_tracks.items()}

# -------------------------------
# VIDEO CROPPING PIPELINE
# -------------------------------
def process_video(video_path):
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    if fps <= 0: fps = CLIP_FPS

    basename = os.path.splitext(os.path.basename(video_path))[0]
    tracker = CentroidTracker()
    frame_idx = 0
    clip_buffers = defaultdict(list)

    print(f"Processing {basename}...")

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        frame_idx += 1
        results = yolo(frame, verbose=False)
        boxes = []

        for r in results[0].boxes:
            if int(r.cls) == 0 and r.conf > CONF_THRESHOLD:  # person class
                boxes.append(r.xyxy[0].cpu().numpy())

        tracked = tracker.update(boxes)

        # store frame crops for each tracked person
        for tid, (x1, y1, x2, y2) in tracked.items():
            crop = frame[int(y1):int(y2), int(x1):int(x2)]
            if crop.size == 0:
                continue
            crop = cv2.resize(crop, (224, 224))
            clip_buffers[tid].append(crop)

            # when we have enough frames, save clip
            if len(clip_buffers[tid]) >= CLIP_FRAMES:
                out_path = os.path.join(OUTPUT_DIR, f"{basename}_person{tid}_clip{frame_idx}.mp4")
                save_clip(clip_buffers[tid][:CLIP_FRAMES], out_path, fps)
                clip_buffers[tid] = []  # reset buffer

    # flush remaining short clips
    for tid, frames in clip_buffers.items():
        if len(frames) >= MIN_FRAMES:
            out_path = os.path.join(OUTPUT_DIR, f"{basename}_person{tid}_final.mp4")
            save_clip(frames, out_path, fps)

    cap.release()

# -------------------------------
# SAVE CLIP TO DISK
# -------------------------------
def save_clip(frames, out_path, fps):
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(out_path, fourcc, fps, (224, 224))
    for f in frames:
        writer.write(f)
    writer.release()
    print(f"Saved: {out_path}")

# -------------------------------
# MAIN
# -------------------------------
if __name__ == "__main__":
    videos = [f for f in os.listdir(SOURCE_DIR) if f.lower().endswith((".mp4", ".avi", ".mov", ".mkv"))]
    for v in videos:
        process_video(os.path.join(SOURCE_DIR, v))

    print("✅ Done! Cropped person clips saved in:", OUTPUT_DIR)
