import tempfile
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.background import BackgroundTask

from core.db import AsyncSessionLocal, get_db
from core.camera_runtime import CAMERA_READERS
from models.camera import Camera
from models.settings import Settings
from models.user import User
from schemas.backup import BackupFile, BackupSchedule, BackupScheduleConfig
from schemas.recording import RecordingSettings
from services.auth import get_current_user
from services.backup import (
    BackupError, backup_lock, create_database_dump,
    get_schedule, next_run, restore_database_dump, save_schedule,
    validate_database_dump,
    recording_backup_lock, create_scheduled_recordings_archive,
)
from services.recording import set_recording_settings
from services.settings import load_settings
from services.rtsp_reader import RTSPCameraReader

router = APIRouter(prefix="/backup", tags=["Backup"])
MAX_UPLOAD_BYTES = 2 * 1024 * 1024 * 1024


def require_admin(user: User) -> None:
    if "system:configure" not in user.permissions:
        raise HTTPException(status_code=403, detail="Forbidden")


@router.get("/database")
async def download_database(user: User = Depends(get_current_user)):
    require_admin(user)
    with tempfile.NamedTemporaryFile(suffix=".dump", delete=False) as tmp:
        path = Path(tmp.name)
    try:
        async with backup_lock:
            await create_database_dump(path)
    except BackupError as exc:
        path.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    filename = f"ai_surveillance_{datetime.now():%Y-%m-%d_%H-%M-%S}.dump"
    return FileResponse(path, filename=filename, media_type="application/octet-stream",
                        background=BackgroundTask(path.unlink, missing_ok=True))


@router.get("/schedule", response_model=BackupSchedule)
async def read_schedule(
    db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user),
):
    require_admin(user)
    return await get_schedule(db)


@router.put("/schedule", response_model=BackupSchedule)
async def update_schedule(
    payload: BackupScheduleConfig,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_admin(user)
    async with backup_lock:
        schedule = BackupSchedule(**payload.model_dump())
        if schedule.enabled:
            schedule.next_run_at = next_run(schedule, datetime.now().astimezone())
        await save_schedule(db, schedule, str(user.id))
    return schedule


@router.get("/recordings/schedule", response_model=BackupSchedule)
async def read_recording_schedule(
    db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user),
):
    require_admin(user)
    return await get_schedule(db, "recording_backup_schedule")


@router.put("/recordings/schedule", response_model=BackupSchedule)
async def update_recording_schedule(
    payload: BackupScheduleConfig,
    db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user),
):
    require_admin(user)
    async with recording_backup_lock:
        schedule = BackupSchedule(**payload.model_dump())
        if schedule.enabled:
            schedule.next_run_at = next_run(schedule, datetime.now().astimezone())
        await save_schedule(db, schedule, str(user.id), key="recording_backup_schedule")
    return schedule


@router.post("/recordings", response_model=BackupFile)
async def create_recording_backup(user: User = Depends(get_current_user)):
    require_admin(user)
    try:
        async with recording_backup_lock:
            path = await create_scheduled_recordings_archive()
    except BackupError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except OSError as exc:
        raise HTTPException(status_code=500, detail="Could not create recording backup") from exc
    stat = path.stat()
    return BackupFile(name=path.name, size_bytes=stat.st_size,
                      created_at=datetime.fromtimestamp(stat.st_mtime).astimezone())


async def reload_runtime_after_restore() -> None:
    for reader in list(CAMERA_READERS.values()):
        reader.stop()
    CAMERA_READERS.clear()
    async with AsyncSessionLocal() as db:
        await load_settings(db)
        row = (await db.execute(select(Settings).where(Settings.name == "recording"))).scalar_one_or_none()
        set_recording_settings(RecordingSettings(**row.settings) if row else RecordingSettings())
        cameras = (await db.execute(
            select(Camera).where(Camera.type == "IP", Camera.enabled == True)
        )).scalars().all()
        for camera in cameras:
            reader = RTSPCameraReader(camera.rtsp, camera.name, camera_id=camera.id)
            CAMERA_READERS[camera.id] = reader
            reader.start()


async def restore_file(path: Path, db: AsyncSession) -> dict[str, str]:
    async with backup_lock:
        try:
            pg_restore = await validate_database_dump(path)
        except BackupError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        # The authorization dependency has loaded the user. Release its locks
        # before pg_restore performs DDL on the same database.
        await db.rollback()
        await db.close()
        try:
            await restore_database_dump(path, pg_restore)
        except BackupError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        finally:
            await reload_runtime_after_restore()
    return {"status": "restored"}


@router.post("/restore-upload")
async def restore_uploaded_backup(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_admin(user)
    if not file.filename or not file.filename.lower().endswith(".dump"):
        raise HTTPException(status_code=422, detail="Choose a .dump file")
    with tempfile.NamedTemporaryFile(suffix=".dump", delete=False) as tmp:
        path = Path(tmp.name)
    try:
        total = 0
        with path.open("wb") as output:
            while chunk := await file.read(1024 * 1024):
                total += len(chunk)
                if total > MAX_UPLOAD_BYTES:
                    raise HTTPException(status_code=413, detail="Backup file is too large")
                output.write(chunk)
        return await restore_file(path, db)
    finally:
        path.unlink(missing_ok=True)
        await file.close()
