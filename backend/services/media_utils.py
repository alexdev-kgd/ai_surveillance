import cv2
import os
import numpy as np
from datetime import datetime
from services.settings import get_settings
from services.anomaly_predictor import (
    analyze_with_yolo,
    analyze_scene,
)

STATIC_DIR = "static/processed"

def analyze_video_file(path: str):
    os.makedirs(STATIC_DIR, exist_ok=True)

    # Output path for annotated video
    output_filename = f"annotated_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
    output_path = os.path.join(STATIC_DIR, output_filename)

    cap = cv2.VideoCapture(path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fourcc = cv2.VideoWriter_fourcc(*"avc1")
    out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))

    total_frames = 0
    detections = []

    settings = get_settings() or {}
    use_yolo = settings["useObjectDetection"]

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        total_frames += 1
        annotated_frame = frame.copy()

        result = (
            analyze_with_yolo(annotated_frame, total_frames)
            if use_yolo
            else analyze_scene(annotated_frame, total_frames)
        )

        detections.extend(result["detections"])

        rgb_annotated = cv2.cvtColor(annotated_frame, cv2.COLOR_BGR2RGB)
        out.write(rgb_annotated)

    cap.release()
    out.release()

    return {
        "total_frames": total_frames,
        "fps": fps,
        "detections": detections,
        "video_path": f"static/processed/{output_filename}"
    }
