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

def _update_frame_jpg(img_bgr):
    global _latest_frame_jpg
    _, buf = cv2.imencode(".jpg", img_bgr, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
    with _frame_lock:
        _latest_frame_jpg = buf.tobytes()

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

def set_event_loop(loop: asyncio.AbstractEventLoop):
    global _event_loop
    _event_loop = loop

def start_video_loop(source=CAMERA_SOURCE):
    """
    Запуск в отдельном потоке. Читает камеру, детектит позы, классифицирует и обновляет frame.
    """
    def _worker():
        global _latest_frame_jpg
        cap = cv2.VideoCapture(source, cv2.CAP_DSHOW)
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
        if not cap.isOpened():
            print("ERROR: camera source not opened:", source)
            return

        with mp_pose.Pose(static_image_mode=False, min_detection_confidence=0.5, min_tracking_confidence=0.5) as pose:
            frame_idx = 0
            while True:
                ret, frame = cap.read()
                if not ret:
                    time.sleep(0.1)
                    continue
                frame_idx += 1
                # resize for performance if needed
                h, w = frame.shape[:2]
                if w > 1280:
                    frame = cv2.resize(frame, (1280, int(1280*h/w)))

                # process pose
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                results = pose.process(frame_rgb)

                landmarks_arr = None
                action = "no_person"
                if results.pose_landmarks:
                    # draw landmarks
                    mp.solutions.drawing_utils.draw_landmarks(frame, results.pose_landmarks, mp_pose.POSE_CONNECTIONS)
                    # build numpy array of landmarks
                    lms = results.pose_landmarks.landmark
                    landmarks_arr = []
                    for lm in lms:
                        landmarks_arr.append((lm.x, lm.y, lm.z))
                    import numpy as np
                    landmarks_arr = np.array(landmarks_arr, dtype=float)
                    action = classifier.predict(landmarks_arr)
                else:
                    action = "no_person"

                # overlay text
                cv2.putText(frame, f"Action: {action}", (10,30), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0,0,255), 2)

                # if dangerous event — broadcast
                if action in ("fall", "fight"):   # 'fight' currently not produced by SimpleActionClassifier but reserved
                    payload = {"event_type": action, "camera": str(source), "frame": frame_idx}
                    broadcast_event(payload)

                # update latest frame jpg
                _update_frame_jpg(frame)

                # small sleep to avoid pegging CPU
                time.sleep(0.01)

        cap.release()

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()
    return thread

# helpers to manage websockets
def register_client(ws):
    with _clients_lock:
        _clients.add(ws)

def unregister_client(ws):
    with _clients_lock:
        if ws in _clients:
            _clients.remove(ws)
