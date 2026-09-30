from fastapi import FastAPI

app = FastAPI(title="AI Surveillance System")

from fastapi.middleware.cors import CORSMiddleware
from core.config import CORS_ORIGINS
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
    expose_headers=["Content-Disposition"],
)

# Register routers
import routers
for r in (
    routers.analyze_video,
    routers.websocket_events,
    routers.websocket_video,
    routers.events,
    routers.auth,
    routers.settings,
    routers.permissions,
    routers.roles,
    routers.audit_log,
    routers.cameras,
    routers.recording,
    routers.backup,
):
    app.include_router(r.router)

# Ensure static folders exist
import os
os.makedirs("static/processed", exist_ok=True)

# Mount static files
from fastapi.staticfiles import StaticFiles
app.mount("/static", StaticFiles(directory="static"), name="static")

# Load settings on startup
from services.settings import load_settings
from core.db import get_db
@app.on_event("startup")
async def load_app_settings():
    async for db in get_db():
        await load_settings(db)
        from models.settings import Settings
        from schemas.recording import RecordingSettings
        from services.recording import set_recording_settings
        from sqlalchemy import select
        row = (await db.execute(select(Settings).where(Settings.name == "recording"))).scalar_one_or_none()
        set_recording_settings(RecordingSettings(**row.settings) if row else RecordingSettings())
        break

from services.rtsp_reader import RTSPCameraReader
from core.camera_runtime import CAMERA_READERS
from models.camera import Camera
from sqlalchemy import select
import asyncio
from services.backup import backup_scheduler

@app.on_event("startup")
async def start_backup_scheduler():
    app.state.backup_task = asyncio.create_task(backup_scheduler())

@app.on_event("shutdown")
async def stop_backup_scheduler():
    task = getattr(app.state, "backup_task", None)
    if task is not None:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)

@app.on_event("startup")
async def init_rtsp_cameras_from_db():
    """
    Get and init RTSP Cameras from DB
    """
    async for db in get_db():
        result = await db.execute(
            select(Camera).where(Camera.type == "IP", Camera.enabled == True)
        )
        cameras = result.scalars().all()

        for cam in cameras:
            if cam.id not in CAMERA_READERS:
                reader = RTSPCameraReader(cam.rtsp, cam.name, camera_id=cam.id)
                reader.start()
                CAMERA_READERS[cam.id] = reader
        break  # берем только один раз сессии

@app.on_event("shutdown")
def shutdown_rtsp_from_db():
    """
    Stop all RTSP cameras
    """
    for reader in CAMERA_READERS.values():
        reader.stop()
    from services.recording import close_all_recordings
    close_all_recordings()

@app.get("/")
def root():
    return {"status": "AI surveillance backend running"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
