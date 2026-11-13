from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from core.audit_action import AuditAction
from core.db import get_db
from models.user import User
from schemas.training import (
    DatasetScanResponse,
    TrainingStartRequest,
    TrainingStatusResponse,
)
from services.auth import get_current_user
from services.audit_log import log_action
from services.training import cancel_training, get_status, scan_classes, start_training

router = APIRouter(prefix="/training", tags=["Training"])


def require_configure(user: User) -> None:
    if "system:configure" not in user.permissions:
        raise HTTPException(status_code=403, detail="Forbidden")


@router.get("/status", response_model=TrainingStatusResponse)
async def training_status(user: User = Depends(get_current_user)):
    require_configure(user)
    return get_status()


@router.get("/classes", response_model=DatasetScanResponse)
async def training_classes(
    train_dir: str = Query(...),
    val_dir: str = Query(...),
    yolo_train_dir: str = Query(""),
    yolo_val_dir: str = Query(""),
    user: User = Depends(get_current_user),
):
    require_configure(user)
    return scan_classes(train_dir, val_dir, yolo_train_dir, yolo_val_dir)


@router.post("/start", response_model=TrainingStatusResponse)
async def training_start(
    payload: TrainingStartRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_configure(user)
    try:
        status = start_training(payload, user_id=str(user.id))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    await log_action(db, user.id, AuditAction.MODEL_TRAINING_START)
    return status


@router.post("/cancel", response_model=TrainingStatusResponse)
async def training_cancel(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_configure(user)
    try:
        status = cancel_training()
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    await log_action(db, user.id, AuditAction.MODEL_TRAINING_CANCEL)
    return status
