import json
import base64
import time
from collections import deque
import numpy as np
import cv2
import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from core.config import FRONTEND_LABELS
from services.event import create_event
from services.mail import add_event
from services.sms import send_sms_notification
from services.settings import get_settings
from services.camera import get_enabled_camera_by_id
from services.anomaly_predictor import (
    analyze_with_yolo,
    analyze_scene,
)
from core.db import get_db
from core.camera_runtime import CAMERA_READERS
from services.rtsp_reader import RTSPCameraReader

router = APIRouter(tags=["Video Stream"])

EVENT_LOG_COOLDOWN_SECONDS = 2.0


def decode_websocket_frame(message: dict) -> np.ndarray | None:
    """Decode both the new binary protocol and legacy base64 text frames."""
    payload = message.get("bytes")
    if payload is None:
        text = message.get("text")
        if text is None:
            return None
        try:
            payload = base64.b64decode(text, validate=True)
        except (ValueError, TypeError):
            return None

    encoded = np.frombuffer(payload, dtype=np.uint8)
    return cv2.imdecode(encoded, cv2.IMREAD_COLOR)


async def stream_usb_camera(
    ws: WebSocket,
    db,
    camera_id: str,
    camera_name: str,
    use_yolo: bool,
    last_logged_at_by_label: dict[str, float],
) -> None:
    """
    Keep camera transport independent from inference.

    The receiver continuously replaces the pending frame, so slow inference never
    creates an ever-growing queue of stale camera frames. The browser renders the
    local MediaStream at camera speed and receives only detection overlays here.
    """
    latest_frame: np.ndarray | None = None
    latest_frame_idx = 0
    received_frames = 0
    processed_frames = 0
    new_frame = asyncio.Event()

    async def receive_frames() -> None:
        nonlocal latest_frame, latest_frame_idx, received_frames

        while True:
            message = await ws.receive()
            if message.get("type") == "websocket.disconnect":
                raise WebSocketDisconnect(message.get("code", 1000))

            frame = decode_websocket_frame(message)
            if frame is None:
                continue

            received_frames += 1
            latest_frame_idx = received_frames
            latest_frame = frame
            new_frame.set()

    async def analyze_latest_frames() -> None:
        nonlocal processed_frames
        last_processed_idx = 0
        completion_times: deque[float] = deque(maxlen=30)

        while True:
            await new_frame.wait()
            new_frame.clear()

            frame = latest_frame
            frame_idx = latest_frame_idx
            if frame is None or frame_idx == last_processed_idx:
                continue

            last_processed_idx = frame_idx
            started_at = time.perf_counter()
            annotated, detections, label, confidence, is_alert = await asyncio.to_thread(
                process_frame,
                frame,
                frame_idx,
                use_yolo,
                False,
            )
            del annotated
            processed_frames += 1

            await save_suspicious_event(
                db=db,
                camera_id=camera_id,
                camera_name=camera_name,
                label=label,
                confidence=confidence,
                frame_idx=frame_idx,
                last_logged_at_by_label=last_logged_at_by_label,
                is_alert=is_alert,
            )

            completed_at = time.perf_counter()
            completion_times.append(completed_at)
            analysis_fps = 0.0
            if len(completion_times) > 1:
                analysis_fps = (len(completion_times) - 1) / max(
                    completion_times[-1] - completion_times[0],
                    1e-6,
                )

            await ws.send_json(
                {
                    "detections": detections,
                    "frameIndex": frame_idx,
                    "sourceWidth": int(frame.shape[1]),
                    "sourceHeight": int(frame.shape[0]),
                    "analysisFps": analysis_fps,
                    "analysisMs": (completed_at - started_at) * 1000.0,
                    "droppedFrames": max(0, received_frames - processed_frames),
                }
            )

    receiver = asyncio.create_task(receive_frames())
    analyzer = asyncio.create_task(analyze_latest_frames())
    tasks = {receiver, analyzer}

    try:
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            exception = task.exception()
            if exception is not None:
                raise exception
        for task in pending:
            task.cancel()
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

@router.websocket("/ws/video/{camera_id}")
async def websocket_video(ws: WebSocket, camera_id: str):
    camera = await get_enabled_camera_by_id(camera_id)
    db = None

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
            await stream_usb_camera(
                ws=ws,
                db=db,
                camera_id=camera_id,
                camera_name=camera_name,
                use_yolo=use_yolo,
                last_logged_at_by_label=last_logged_at_by_label,
            )

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
                annotated, detections, label, confidence, is_alert = process_frame(
                    frame, frame_idx, use_yolo, annotate=False
                )

                await save_suspicious_event(
                    db=db,
                    camera_id=camera_id,
                    camera_name=camera_name,
                    label=label,
                    confidence=confidence,
                    frame_idx=frame_idx,
                    last_logged_at_by_label=last_logged_at_by_label,
                    is_alert=is_alert,
                )

                await send_frame(ws, annotated, detections)
                await asyncio.sleep(0.2)  # ~5 FPS

    except WebSocketDisconnect:
        print("Client disconnected")
    finally:
        if db is not None:
            await db.close()


def process_frame(frame, frame_idx, use_yolo, annotate: bool = True):
    output_frame = frame.copy() if annotate else frame

    result = (
        analyze_with_yolo(output_frame, frame_idx, annotate=annotate)
        if use_yolo
        else analyze_scene(output_frame, frame_idx, annotate=annotate)
    )

    return (
        result["frame_data"],
        result["detections"],
        result["label"],
        result["confidence"],
        result.get("is_alert", False),
    )

async def save_suspicious_event(
    db,
    camera_id: str,
    camera_name: str,
    label: str,
    confidence: float,
    frame_idx: int,
    last_logged_at_by_label: dict[str, float],
    is_alert: bool = False,
):
    # Only persist / notify when alert threshold is met (stricter than display)
    if label == FRONTEND_LABELS["normal"] or not is_alert:
        return

    now = time.monotonic()
    last_logged_at = last_logged_at_by_label.get(label, 0.0)
    if now - last_logged_at < EVENT_LOG_COOLDOWN_SECONDS:
        return

    add_event(f"{label} on {camera_name}")
    send_sms_notification(f"{label} на камере {camera_name}")

    await create_event(
        db=db,
        event_type=label,
        camera=camera_name,
        details=json.dumps(
            {
                "ID камеры": camera_id,
                "Кадр": frame_idx,
                "Уверенность": round(float(confidence), 4),
                "is_alert": True,
            },
            ensure_ascii=False,
        ),
    )
    last_logged_at_by_label[label] = now

    last_logged_at_by_label[label] = now

async def send_frame(ws: WebSocket, frame, detections):
    _, encoded = cv2.imencode(".jpg", frame)
    frame_b64 = base64.b64encode(encoded).decode("utf-8")

    await ws.send_json({
        "frame": frame_b64,
        "detections": detections,
    })
