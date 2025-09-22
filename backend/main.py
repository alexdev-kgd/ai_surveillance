# backend/main.py
import os
import tempfile
import uvicorn
import cv2
import mediapipe as mp
import asyncio
from fastapi import FastAPI, UploadFile, File, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse, JSONResponse
from video_processor import start_video_loop, set_event_loop, get_mjpeg_generator, register_client, unregister_client
from db import get_recent_events
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="AI Surveillance System")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # или ["*"] для всех источников
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# запускаем процессор камеры при старте приложения
@app.on_event("startup")
def startup_event():
    loop = asyncio.get_event_loop()
    set_event_loop(loop)
    # можно поменять источник: 0 или rtsp://...
    start_video_loop(source=0)

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

@app.get("/video_feed")
def video_feed():
    """
    MJPEG stream; browser can render <img src="/video_feed">
    """
    return StreamingResponse(get_mjpeg_generator(), media_type='multipart/x-mixed-replace; boundary=frame')

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

@app.get("/events/recent")
def recent_events():
    return get_recent_events(limit=50)

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
