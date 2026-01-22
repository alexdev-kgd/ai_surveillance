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
from routers import analyze_video, websocket_events, websocket_video, events, auth, settings, permissions, roles, audit_log
app.include_router(events.router)
app.include_router(analyze_video.router)
app.include_router(websocket_events.router)
app.include_router(websocket_video.router)
app.include_router(auth.router)
app.include_router(settings.router)
app.include_router(permissions.router)
app.include_router(roles.router)
app.include_router(audit_log.router)

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

@app.get("/")
def root():
    return {"status": "AI surveillance backend running"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
