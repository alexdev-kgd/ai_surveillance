from typing import Dict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from models.settings import Settings
from core.config import DEFAULT_SETTINGS

_cached_settings: Dict | None = None

async def load_settings(db: AsyncSession):
    global _cached_settings

    stmt = select(Settings).where(Settings.name == "default")
    result = await db.execute(stmt)
    settings = result.scalars().first()

    _cached_settings = settings.settings if settings else DEFAULT_SETTINGS

def get_settings():
    return _cached_settings or DEFAULT_SETTINGS
