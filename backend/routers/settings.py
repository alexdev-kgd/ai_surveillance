from fastapi import HTTPException, APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from core.db import get_db
from core.audit_action import AuditAction
from core.config import ACTIONS
from schemas.settings import Settings as SettingsSchema
from models.settings import Settings
from models.user import User
from services.auth import get_current_user
from services.settings import load_settings
from services.audit_log import log_action

router = APIRouter(prefix="/settings", tags=["Settings"])

@router.get("", response_model=SettingsSchema)
async def get_settings(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    stmt = select(Settings).where(Settings.name == "default")
    result = await db.execute(stmt)

    settings = result.scalars().first()

    if not settings:
        return SettingsSchema(
            detection=ACTIONS,
            useObjectDetection=True,
        )

    await load_settings(db)
    await log_action(db, user.id, AuditAction.AI_SETTINGS_ACCESS)

    return SettingsSchema(
        detection=settings.settings["detection"],
        useObjectDetection=settings.settings["useObjectDetection"],
    )

@router.put("", response_model=SettingsSchema)
async def update_settings(
    payload: SettingsSchema,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if "system:configure" not in user.permissions:
        raise HTTPException(status_code=403, detail="Forbidden")

    stmt = select(Settings).where(Settings.name == "default")
    result = await db.execute(stmt)

    settings = result.scalars().first()

    if settings:
        settings.settings = payload.dict()
        settings.updated_by = str(user.id)
    else:
        settings = Settings(
            name="default",
            settings=payload.dict(),
            updated_by=str(user.id)
        )
        db.add(settings)

    await db.commit()
    await db.refresh(settings)

    await load_settings(db)
    await log_action(db, user.id, AuditAction.AI_SETTINGS_UPDATE)

    return payload