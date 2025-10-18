import cv2
import os
import numpy as np
from datetime import datetime
from models.yolo_detector import yolo_model
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
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))

    total_frames = 0
    detections_summary = []

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        total_frames += 1
        yolo_results = yolo_model(frame)
        annotated_frame = frame.copy()

        for r in yolo_results[0].boxes:
            cls_id = int(r.cls)
            if cls_id == 0:  # person
                x1, y1, x2, y2 = map(int, r.xyxy[0].tolist())
                person_crop = frame[y1:y2, x1:x2]
                img = cv2.resize(person_crop, (224, 224))
                label, confidence = anomaly_model_predict(img)
                color = (0, 255, 0) if label == "normal" else (0, 0, 255)

                cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), color, 2)
                cv2.putText(
                    annotated_frame,
                    f"{label} ({confidence:.2f})",
                    (x1, y1 - 10),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    color,
                    2,
                )

                detections_summary.append({
                    "frame": total_frames,
                    "bbox": [x1, y1, x2, y2],
                    "label": label,
                    "confidence": confidence
                })

        out.write(annotated_frame)

    cap.release()
    out.release()

    return {
        "total_frames": total_frames,
        "detections": detections_summary,
        "video_path": f"/static/processed/{output_filename}"
    }