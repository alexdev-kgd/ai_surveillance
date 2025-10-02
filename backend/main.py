import os
import tempfile
import uvicorn
import cv2
import mediapipe as mp
import torch
import json
import base64
import io
import numpy as np
import torch.nn.functional as F
from PIL import Image
from fastapi import FastAPI, UploadFile, File, WebSocket, WebSocketDisconnect
from video_processor import register_client, unregister_client
from db import get_recent_events
from fastapi.middleware.cors import CORSMiddleware
from ultralytics import YOLO
import torch.nn as nn

app = FastAPI(title="AI Surveillance System")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # или ["*"] для всех источников
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load YOLOv8 for person detection
yolo_model = YOLO("yolov8n.pt")  # small & fast, trained on COCO

# Load anomaly model
video_model = torch.hub.load("facebookresearch/pytorchvideo", "slow_r50", pretrained=False)
video_model.blocks[-1].proj = nn.Linear(video_model.blocks[-1].proj.in_features, 1)
checkpoint = torch.load("suspicious_actions.pth", map_location="cpu")
video_model.load_state_dict(checkpoint["model_state_dict"])
video_model.eval()

# Сколько кадров копим на один "батч"
FRAME_WINDOW = 16

@app.get("/")
def root():
    return {"status": "AI surveillance backend running"}

@app.post("/analyze/video/")
async def analyze_video(file: UploadFile = File(...)):
    """
    Приём видеофайла, простая обработка: извлечение поз и базовая статистика.
    (Можно заменить или расширить вызовом heavy model)
    """
    suffix = os.path.splitext(file.filename)[-1]
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name

    # Используем тот же поток обработки: анализ через MediaPipe в клиентском режиме
    mp_pose = mp.solutions.pose

    total_frames = 0
    frames_with_people = 0
    actions = {}

    with mp_pose.Pose(static_image_mode=False, min_detection_confidence=0.5, min_tracking_confidence=0.5) as pose:
        cap = cv2.VideoCapture(tmp_path)
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            total_frames += 1
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = pose.process(frame_rgb)
            if results.pose_landmarks:
                frames_with_people += 1
            # optionally could run classifier here (reuse classifier from video_processor)
    cap.release()
    os.remove(tmp_path)

    return {
        "total_frames": total_frames,
        "frames_with_people": frames_with_people,
        "people_percent": round(frames_with_people/total_frames*100, 2) if total_frames>0 else 0
    }

# WebSocket endpoint для событий
@app.websocket("/ws/events")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    register_client(websocket)
    try:
        while True:
            # ожидание сообщений от клиента (можно использовать ping/pong)
            data = await websocket.receive_text()
            # echo or ignore; client might send {"cmd":"ping"}
            await websocket.send_text(f"server received: {data}")
    except WebSocketDisconnect:
        unregister_client(websocket)

@app.websocket("/ws/video/")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()

    buffer = []  # храним кадры

    with open("kinetics400_labels.json") as f:
        name_to_id = json.load(f)
        id_to_name = {v: k.strip('"') for k, v in name_to_id.items()}

    try:
        while True:
            data = await ws.receive_text()

            # кадр приходит как base64 (jpeg/png)
            img_bytes = base64.b64decode(data)
            img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
            frame = np.array(img)

            # ========= YOLO =========

            # Detect persons with YOLO
            yolo_results = yolo_model(frame)

            annotated = frame.copy()
            detections = []
            for r in yolo_results[0].boxes:
                cls_id = int(r.cls)
                if cls_id == 0:  # COCO class 0 = person
                    x1, y1, x2, y2 = map(int, r.xyxy[0].tolist())
                    person_crop = frame[y1:y2, x1:x2]

                    # Classify crop
                    label = anomaly_model_predict(person_crop)

                    # Color: green = normal, red = suspicious
                    color = (0, 255, 0) if label == "normal" else (255, 0, 0)

                    # Draw bounding box
                    cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
                    cv2.putText(
                        annotated, label, (x1, y1 - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2
                    )

                    detections.append({
                        "bbox": [x1, y1, x2, y2],
                        "label": label
                    })

            # Encode annotated frame → base64 for sending back
            rgb_annotated_frame = cv2.cvtColor(annotated, cv2.COLOR_BGR2RGB)
            _, buffer = cv2.imencode(".jpg", rgb_annotated_frame)
            frame_b64 = base64.b64encode(buffer).decode("utf-8")

            await ws.send_json({
                "detections": detections,
                "frame": frame_b64
            })
            
            # ========= Anomaly Detection =========
            
            # resize до 224x224
            frame = cv2.resize(frame, (224, 224))
            buffer.append(frame)

            if len(buffer) >= FRAME_WINDOW:
                # Преобразуем в тензор (T, C, H, W)
                video_tensor = torch.tensor(buffer).permute(3, 0, 1, 2).unsqueeze(0).float()
                buffer = []  # очистка

                with torch.no_grad():
                    preds = video_model(video_tensor)
                    probs = F.softmax(preds, dim=-1)
                    pred_idx = torch.argmax(probs, dim=-1).item()
                    print(pred_idx)
                    action_name = id_to_name[pred_idx]
                    confidence = float(probs[0, pred_idx])

                    # Get top3 predictions
                    top5 = torch.topk(preds, k=3).indices

                    # Map indices -> labels
                    for idx in top5[0]:
                        label = id_to_name[idx.item()]
                        print(idx.item(), label)

                # Возвращаем на фронт предсказание
                await ws.send_json({
                    "prediction": label,
                    "confidence": confidence
                })

    except WebSocketDisconnect:
        print("Client disconnected")

def anomaly_model_predict(crop):
    # Placeholder for actual anomaly detection logic
    # For demo purposes, randomly return "normal" or "suspicious"
    import random
    return random.choice(["normal", "suspicious"])

@app.get("/events/recent")
def recent_events():
    return get_recent_events(limit=50)

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
