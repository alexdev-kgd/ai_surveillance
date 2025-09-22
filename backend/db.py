from sqlalchemy import create_engine, Table, Column, Integer, String, MetaData, DateTime, select
from sqlalchemy.sql import func
from sqlalchemy.engine import Engine

DATABASE_URL = "sqlite:///./ais_events.db"  # можно заменить на postgresql://user:pass@host/db

engine: Engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
metadata = MetaData()

events = Table(
    "events", metadata,
    Column("id", Integer, primary_key=True),
    Column("event_type", String, nullable=False),
    Column("camera", String, nullable=True),
    Column("details", String, nullable=True),
    Column("timestamp", DateTime, server_default=func.now())
)

metadata.create_all(engine)

def log_event(event_type: str, camera: str = None, details: str = None):
    with engine.begin() as conn:
        conn.execute(events.insert().values(event_type=event_type, camera=camera, details=details))

def get_recent_events(limit: int = 50):
    with engine.begin() as conn:
        q = select(events).order_by(events.c.timestamp.desc()).limit(limit)
        res = conn.execute(q).mappings().all()
        return [dict(r) for r in res]
