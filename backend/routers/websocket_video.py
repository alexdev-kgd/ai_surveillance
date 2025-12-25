import json
import base64
import io
import numpy as np
import cv2
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from PIL import Image
from services.anomaly_predictor import anomaly_model_predict
from config import KINETICS_LABELS
from services.event import create_event
from db import SessionLocal

router = APIRouter(tags=["Video Stream"])

@router.websocket("/ws/video/")
async def websocket_video(ws: WebSocket):
    await ws.accept()

    db = SessionLocal()

    with open(KINETICS_LABELS) as f:
        name_to_id = json.load(f)
        id_to_name = {v: k.strip('"') for k, v in name_to_id.items()}

    try:
        while True:
            data = await ws.receive_text()
            img_bytes = base64.b64decode(data)
            img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
            frame = np.array(img)

            annotatannotated_frameed = frame.copy()
            detections = []

            label, _ = anomaly_model_predict(annotated_frame)
            color = (0, 255, 0) if label == "normal" else (255, 0, 0)
            cv2.putText(annotated_frame, label, (x1, y1 - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
            detections.append({"label": label})

            if label != "normal":
                create_event(db=db, event_type=label,
                                camera="Camera 1", details="Автоопределено")

            rgb_annotated = cv2.cvtColor(annotated_frame, cv2.COLOR_BGR2RGB)
            _, encoded = cv2.imencode(".jpg", rgb_annotated)
            frame_b64 = base64.b64encode(encoded).decode("utf-8")

            await ws.send_json({"detections": detections, "frame": frame_b64})

    except WebSocketDisconnect:
        print("Client disconnected")
    finally:
        db.close()
