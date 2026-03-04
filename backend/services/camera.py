from sqlalchemy import select
from core.db import get_db
from models.camera import Camera

async def get_enabled_camera_by_id(camera_id: str) -> dict | None:
    async for db in get_db():
        result = await db.execute(
            select(Camera).where(Camera.id == camera_id, Camera.enabled == True)
        )
        camera_row = result.scalar_one_or_none()

        if camera_row is None:
            return None

        return {
            "type": camera_row.type,
            "name": camera_row.name,
            "rtsp": camera_row.rtsp,
        }

    return None
