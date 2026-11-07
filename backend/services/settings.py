from typing import Dict, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm.attributes import flag_modified
from models.settings import Settings
from core.config import DEFAULT_SETTINGS, LEGACY_ACTION_ALIASES

_cached_settings: Dict | None = None


def normalize_detection(detection: Dict) -> Tuple[Dict, bool]:
    """Rename legacy action keys. Existing canonical keys are kept."""
    normalized = dict(detection)
    changed = False
    for legacy, current in LEGACY_ACTION_ALIASES.items():
        if legacy not in normalized:
            continue
        changed = True
        legacy_value = normalized.pop(legacy)
        if current not in normalized:
            normalized[current] = legacy_value
    return normalized, changed


def detection_action_config(detection: Dict, action_key: str):
    config = detection.get(action_key)
    if config:
        return config
    for legacy, current in LEGACY_ACTION_ALIASES.items():
        if current == action_key and legacy in detection:
            return detection[legacy]
    return None


async def load_settings(db: AsyncSession):
    global _cached_settings

    stmt = select(Settings).where(Settings.name == "default")
    result = await db.execute(stmt)
    settings = result.scalars().first()

    if not settings:
        _cached_settings = DEFAULT_SETTINGS
        return

    stored = dict(settings.settings or {})
    detection, changed = normalize_detection(stored.get("detection") or {})
    if changed:
        stored["detection"] = detection
        settings.settings = stored
        flag_modified(settings, "settings")
        await db.commit()

    _cached_settings = stored

def get_settings():
    return _cached_settings or DEFAULT_SETTINGS
