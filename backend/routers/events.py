from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from models.event import Event
from core.db import get_db
from services.event import create_event, get_events

router = APIRouter(prefix="/events", tags=["Events"])

@router.get("/", response_model=List[dict])
async def read_events(db: AsyncSession = Depends(get_db)):
    events = await get_events(db)
    return [
        {
            "id": e.id,
            "event_type": e.event_type,
            "camera": e.camera,
            "timestamp": e.timestamp.isoformat(),
            "details": e.details
        }
        for e in events
    ]

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
