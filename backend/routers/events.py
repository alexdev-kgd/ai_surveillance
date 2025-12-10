# routers/events.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List
from models.event import Event
from db import SessionLocal
from services.event import create_event, get_events

router = APIRouter(prefix="/events", tags=["Events"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/", response_model=List[dict])
def read_events(db: Session = Depends(get_db)):
    events = get_events(db)
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
def add_event(event_type: str, camera: str = None, details: str = None, db: Session = Depends(get_db)):
    ev = create_event(db, event_type, camera, details)
    return {
            "id": ev.id,
            "event_type": ev.event_type,
            "timestamp": ev.timestamp.isoformat()
            }
