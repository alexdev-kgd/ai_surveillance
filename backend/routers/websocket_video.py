import json
import base64
import io
import time
import numpy as np
import cv2
import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from PIL import Image
from core.config import FRONTEND_LABELS
from core.cameras import CAMERAS
from services.event import create_event
from services.mail import add_event as add_email_event, send_sms_notification
from services.settings import get_settings
from services.anomaly_predictor import (
    analyze_with_yolo,
    analyze_scene,
)
from core.db import get_db
from models.camera import Camera
from sqlalchemy import select
from core.camera_runtime import CAMERA_READERS
from services.rtsp_reader import RTSPCameraReader

router = APIRouter(tags=["Video Stream"])

EVENT_LOG_COOLDOWN_SECONDS = 2.0

@router.websocket("/ws/video/{camera_id}")
async def websocket_video(ws: WebSocket, camera_id: str):
    camera = CAMERAS.get(camera_id)
    db = None

    if camera is None:
        async for session in get_db():
            db = session
            result = await db.execute(
                select(Camera).where(Camera.id == camera_id, Camera.enabled == True)
            )
            camera_row = result.scalar_one_or_none()
            break

        if camera_row:
            camera = {
                "type": camera_row.type,
                "name": camera_row.name,
                "rtsp": camera_row.rtsp,
            }

    if camera is None:
        await ws.close(code=1008)
        return

    await ws.accept()

    if db is None:
        async for session in get_db():
            db = session
            break

    settings = get_settings() or {}
    use_yolo = settings.get("useObjectDetection", True)

    frame_idx = 0
    last_logged_at_by_label: dict[str, float] = {}
    camera_name = camera.get("name", camera_id)

    try:
        if str(camera["type"]).upper() in ("WEBCAM", "USB"):
            while True:
                data = await ws.receive_text()

                img_bytes = base64.b64decode(data)
                img = Image.open(io.BytesIO(img_bytes))

                frame = np.array(img)
                frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

                frame_idx += 1

                annotated, detections, label, confidence = process_frame(
                    frame, frame_idx, use_yolo
                )

                await save_suspicious_event(
                    db=db,
                    camera_id=camera_id,
                    camera_name=camera_name,
                    label=label,
                    confidence=confidence,
                    frame_idx=frame_idx,
                    last_logged_at_by_label=last_logged_at_by_label,
                )

                await send_frame(ws, annotated, detections)

        else:
            # ==========================
            # IP CAMERA: shared background reader
            # ==========================
            reader = CAMERA_READERS.get(camera_id)
            if reader is None:
                rtsp_url = camera.get("rtsp")
                if not rtsp_url:
                    await ws.send_json(
                        {"error": f"Camera {camera.get('name', camera_id)} has no RTSP url"}
                    )
                    await ws.close(code=1011)
                    return

                reader = RTSPCameraReader(rtsp_url, camera_name)
                reader.start()
                CAMERA_READERS[camera_id] = reader

            if not reader.running:
                reader.start()

            while True:
                frame = reader.get_frame()
                if frame is None:
                    await asyncio.sleep(0.1)
                    continue

                frame_idx += 1
                annotated, detections, label, confidence = process_frame(
                    frame, frame_idx, use_yolo
                )

                await save_suspicious_event(
                    db=db,
                    camera_id=camera_id,
                    camera_name=camera_name,
                    label=label,
                    confidence=confidence,
                    frame_idx=frame_idx,
                    last_logged_at_by_label=last_logged_at_by_label,
                )

                await send_frame(ws, annotated, detections)
                await asyncio.sleep(0.2)  # ~5 FPS

    except WebSocketDisconnect:
        print("Client disconnected")
    finally:
        if db is not None:
            await db.close()


def process_frame(frame, frame_idx, use_yolo):
    annotated_frame = frame.copy()

    result = (
        analyze_with_yolo(annotated_frame, frame_idx)
        if use_yolo
        else analyze_scene(annotated_frame, frame_idx)
    )

    return (
        result["frame_data"],
        result["detections"],
        result["label"],
        result["confidence"],
    )

async def save_suspicious_event(
    db,
    camera_id: str,
    camera_name: str,
    label: str,
    confidence: float,
    frame_idx: int,
    last_logged_at_by_label: dict[str, float],
):
    if label == FRONTEND_LABELS["normal"]:
        return

    now = time.monotonic()
    last_logged_at = last_logged_at_by_label.get(label, 0.0)
    if now - last_logged_at < EVENT_LOG_COOLDOWN_SECONDS:
        return

    add_email_event(f"{label} on Camera 1")
    send_sms_notification(label)

    await create_event(
        db=db,
        event_type=label,
        camera=camera_name,
        details=json.dumps(
            {
                "ID камеры": camera_id,
                "Кадр": frame_idx,
                "Уверенность": round(float(confidence), 4),
            },
            ensure_ascii=False,
        ),
    )

    last_logged_at_by_label[label] = now

async def send_frame(ws: WebSocket, frame, detections):
    _, encoded = cv2.imencode(".jpg", frame)
    frame_b64 = base64.b64encode(encoded).decode("utf-8")

    await ws.send_json({
        "frame": frame_b64,
        "detections": detections,
    })
