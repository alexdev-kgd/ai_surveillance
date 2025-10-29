# backend/video_processor.py
import cv2
import threading
import time
import base64
import asyncio
import json
import mediapipe as mp
from typing import Set
from action_recognizer import SimpleActionClassifier
from db import log_event

mp_pose = mp.solutions.pose

# глобальные объекты состояния (простейшая реализация)
_latest_frame_jpg = None           # bytes
_frame_lock = threading.Lock()
_clients = set()                    # set of WebSocket objects (FastAPI WebSocket)
_clients_lock = threading.Lock()
_event_loop = None

# Источник камеры: 0 или rtsp://...
CAMERA_SOURCE = 0

classifier = SimpleActionClassifier()

def get_mjpeg_generator():
    """
    Возвращает генератор для StreamingResponse
    """
    def gen():
        while True:
            with _frame_lock:
                frame = _latest_frame_jpg
            if frame is None:
                # если еще нет кадра — подождать
                time.sleep(0.05)
                continue
            yield (b"--frame\r\n"
                   b"Content-Type: image/jpeg\r\n\r\n" + frame + b"\r\n")
            time.sleep(0.03)  # ~30 FPS max throttle
    return gen()

def broadcast_event(payload: dict):
    """
    Отсылает JSON payload всем подключенным websocket-клиентам (асинхронно)
    """
    # логируем в БД
    try:
        log_event(payload.get("event_type", "event"), 
                  camera=payload.get("camera"),
                  details=json.dumps(payload))
    except Exception:
        pass

    with _clients_lock:
        to_send = list(_clients)

    async def _send_all():
        disconnected = []
        for ws in to_send:
            try:
                await ws.send_json(payload)
            except Exception:
                disconnected.append(ws)
        # удалить отключенные
        if disconnected:
            with _clients_lock:
                for w in disconnected:
                    _clients.discard(w)

    if _event_loop is not None:
        asyncio.run_coroutine_threadsafe(_send_all(), _event_loop)

# helpers to manage websockets
def register_client(ws):
    with _clients_lock:
        _clients.add(ws)

def unregister_client(ws):
    with _clients_lock:
        if ws in _clients:
            _clients.remove(ws)
