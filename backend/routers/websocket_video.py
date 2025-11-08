import json
import base64
import io
import numpy as np
import cv2
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from PIL import Image
from models.yolo_detector import yolo_model
from services.anomaly_predictor import anomaly_model_predict
from config import KINETICS_LABELS
import services.mail as mail

router = APIRouter(tags=["Video Stream"])

@router.websocket("/ws/video/")
async def websocket_video(ws: WebSocket):
    await ws.accept()

    with open(KINETICS_LABELS) as f:
        name_to_id = json.load(f)
        id_to_name = {v: k.strip('"') for k, v in name_to_id.items()}

    try:
        while True:
            data = await ws.receive_text()
            img_bytes = base64.b64decode(data)
            img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
            frame = np.array(img)

            yolo_results = yolo_model(frame)
            annotated = frame.copy()
            detections = []

            for r in yolo_results[0].boxes:
                cls_id = int(r.cls)
                if cls_id == 0:
                    x1, y1, x2, y2 = map(int, r.xyxy[0].tolist())
                    person_crop = frame[y1:y2, x1:x2]

                    label, _ = anomaly_model_predict(person_crop)
                    color = (0, 255, 0) if label == "normal" else (255, 0, 0)
                    
                    cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
                    cv2.putText(annotated, label, (x1, y1 - 10),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
                    
                    detections.append({"bbox": [x1, y1, x2, y2], "label": label})

                    mail.add_event(f"{label}")

            rgb_annotated = cv2.cvtColor(annotated, cv2.COLOR_BGR2RGB)
            _, encoded = cv2.imencode(".jpg", rgb_annotated)
            frame_b64 = base64.b64encode(encoded).decode("utf-8")

            await ws.send_json({"detections": detections, "frame": frame_b64})

    except WebSocketDisconnect:
        print("Client disconnected")
