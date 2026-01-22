import json
import base64
import io
import numpy as np
import cv2
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from PIL import Image
from services.anomaly_predictor import anomaly_model_predict
from core.config import KINETICS_LABELS, FRONTEND_LABELS
from services.event import create_event
from services.settings import get_settings
from services.anomaly_predictor import (
    analyze_with_yolo,
    analyze_scene,
)
from core.db import get_db

router = APIRouter(tags=["Video Stream"])

@router.websocket("/ws/video")
async def websocket_video(ws: WebSocket):
    await ws.accept()

    db = get_db()

    settings = get_settings() or {}
    use_yolo = settings.get("useObjectDetection", True)

    with open(KINETICS_LABELS) as f:
        name_to_id = json.load(f)
        id_to_name = {v: k.strip('"') for k, v in name_to_id.items()}

    try:
        frame_idx = 0

        while True:
            data = await ws.receive_text()
            img_bytes = base64.b64decode(data)
            img = Image.open(io.BytesIO(img_bytes))
            frame = np.array(img)
            frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

            annotated_frame = frame.copy()
            detections = []
            frame_idx += 1

            result = (
                analyze_with_yolo(annotated_frame, frame_idx)
                if use_yolo
                else analyze_scene(annotated_frame, frame_idx)
            )

            label = result["label"]
            confidence = result["confidence"]
            detections = result["detections"]

            if label != FRONTEND_LABELS["normal"]:
                create_event(db=db, event_type=label,
                                camera="Camera 1", details="Автоопределено")

            annotated_frame = result['frame_data']
            _, encoded = cv2.imencode(".jpg", annotated_frame)
            frame_b64 = base64.b64encode(encoded).decode("utf-8")

            await ws.send_json({
                "detections": detections,
                "frame": frame_b64
            })

    except WebSocketDisconnect:
        print("Client disconnected")
    finally:
        db.close()
