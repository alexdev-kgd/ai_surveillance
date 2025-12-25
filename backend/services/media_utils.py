import cv2
import os
import numpy as np
from datetime import datetime
from services.anomaly_predictor import anomaly_model_predict

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
    detections_summary = []

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        total_frames += 1
        annotated_frame = frame.copy()

        # Action prediction
        label, confidence = anomaly_model_predict(annotated_frame)
        color = (0, 255, 0) if label == "normal" else (0, 0, 255)
        cv2.putText(
            annotated_frame,
            f"{label} ({confidence:.2f})",
            (10, 20),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            color,
            2,
        )

        detections_summary.append({
            "frame": total_frames,
            "label": label,
            "confidence": confidence,
        })

        out.write(annotated_frame)

    cap.release()
    out.release()

    return {
        "total_frames": total_frames,
        "fps": fps,
        "detections": detections_summary,
        "video_path": f"/static/processed/{output_filename}"
    }
