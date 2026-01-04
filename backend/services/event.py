from sqlalchemy.ext.asyncio import AsyncSession
from models.event import Event
from datetime import datetime

async def create_event(db: AsyncSession,
                       event_type: str,
                       camera: str = None,
                       details: str = None):
    ev = Event(event_type=event_type,
               camera=camera,
               timestamp=datetime.utcnow(),
               details=details)

    db.add(ev)
    await db.commit()
    await db.refresh(ev)

    return ev

async def get_events(db: AsyncSession, limit: int = 100):
    stmt = (
        select(Event)
        .order_by(Event.timestamp.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)

    return result.scalars().all()