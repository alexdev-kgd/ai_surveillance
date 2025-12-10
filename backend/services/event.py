from sqlalchemy.orm import Session
from models.event import Event
from datetime import datetime

def create_event(db: Session, event_type: str, camera: str = None, details: str = None):
    ev = Event(event_type=event_type, camera=camera, timestamp=datetime.utcnow(), details=details)
    db.add(ev)
    db.commit()
    db.refresh(ev)
    return ev

def get_events(db: Session, limit: int = 100):
    return db.query(Event).order_by(Event.timestamp.desc()).limit(limit).all()
