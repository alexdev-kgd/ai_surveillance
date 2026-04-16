from fastapi import FastAPI

app = FastAPI(title="AI Surveillance System")

from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
        break

from services.rtsp_reader import RTSPCameraReader
from core.camera_runtime import CAMERA_READERS
from models.camera import Camera
from sqlalchemy import select
import asyncio
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
                reader = RTSPCameraReader(cam.rtsp, cam.name)
                print(cam.name)
                print(cam.rtsp)
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

@app.get("/")
def root():
    return {"status": "AI surveillance backend running"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
