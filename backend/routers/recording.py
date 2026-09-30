from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.db import get_db
from models.camera import Camera
from models.settings import Settings
from models.user import User
from schemas.recording import RecordingSettings
from services.auth import get_current_user
from services.recording import get_recording_settings, resolve_recordings_dir, set_recording_settings

router = APIRouter(prefix="/recording", tags=["Recording"])


def require_admin(user: User):
    if "system:configure" not in user.permissions:
        raise HTTPException(status_code=403, detail="Forbidden")


@router.get("", response_model=RecordingSettings)
async def get_recording(user: User = Depends(get_current_user)):
    require_admin(user)
    return get_recording_settings()


@router.put("", response_model=RecordingSettings)
async def update_recording(
    payload: RecordingSettings,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_admin(user)
    cameras = (await db.execute(select(Camera.id))).scalars().all()
    if set(payload.camera_enabled) - set(cameras):
        raise HTTPException(status_code=422, detail="Unknown camera")
    try:
        directory = resolve_recordings_dir(payload.directory)
        directory.mkdir(parents=True, exist_ok=True)
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=422, detail="Invalid recording directory") from exc
    row = (await db.execute(select(Settings).where(Settings.name == "recording"))).scalar_one_or_none()
    if row is None:
        row = Settings(name="recording", settings=payload.dict(), updated_by=str(user.id))
        db.add(row)
    else:
        row.settings = payload.dict()
        row.updated_by = str(user.id)
    await db.commit()
    set_recording_settings(payload)
    return payload
