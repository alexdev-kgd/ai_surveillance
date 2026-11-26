from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from models.event import Event
from core.db import get_db
from services.event import create_event
from services.settings import get_action_label
from utils.convert_to_naive_utc import convert_to_naive_utc

router = APIRouter(prefix="/events", tags=["Events"])

@router.get("/")
async def read_events(
    page: int = Query(0, ge=0),
    size: int = Query(10, ge=1, le=100),
    search: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    filters = [Event.event_type.notin_(["normal", "Нормальное поведение"])]

    if action:
        filters.append(Event.event_type.in_([action, get_action_label(action)]))
    if date_from:
        filters.append(Event.timestamp >= convert_to_naive_utc(date_from))
    if date_to:
        filters.append(Event.timestamp <= convert_to_naive_utc(date_to))
    if search:
        pattern = f"%{search.strip()}%"
        filters.append(or_(
            Event.event_type.ilike(pattern),
            Event.camera.ilike(pattern),
            Event.details.ilike(pattern),
        ))

    where_clause = and_(*filters)
    total = (await db.execute(
        select(func.count(Event.id)).where(where_clause)
    )).scalar_one()
    result = await db.execute(
        select(Event)
        .where(where_clause)
        .order_by(desc(Event.timestamp), desc(Event.id))
        .offset(page * size)
        .limit(size)
    )
    events = result.scalars().all()
    return {
        "items": [
            {
                "id": event.id,
                "event_type": event.event_type,
                "camera": event.camera,
                "timestamp": event.timestamp.isoformat(),
                "details": event.details,
            }
            for event in events
        ],
        "total": total,
        "page": page,
        "size": size,
    }

@router.post("/")
async def add_event(event_type: str,
                    camera: str = None,
                    details: str = None,
                    db: AsyncSession = Depends(get_db)):
    ev = await create_event(db, event_type, camera, details)
    return {
            "id": ev.id,
            "event_type": ev.event_type,
            "timestamp": ev.timestamp.isoformat()
            }
