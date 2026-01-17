from fastapi import HTTPException, APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from core.db import get_db
from schemas.settings import Settings as SettingsSchema
from models.settings import Settings
from models.user import User
from services.auth import get_current_user
from services.settings import load_settings
from core.config import ACTIONS

router = APIRouter(prefix="/settings", tags=["Settings"])

@router.get("", response_model=SettingsSchema)
async def get_settings(db: AsyncSession = Depends(get_db)):
    stmt = select(Settings).where(Settings.name == "default")
    result = await db.execute(stmt)

    settings = result.scalars().first()

    if not settings:
        return SettingsSchema(
            detection=ACTIONS
        )

    await load_settings(db)

    return SettingsSchema(
        detection=settings.settings["detection"]
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

    return payload