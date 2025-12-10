from sqlalchemy import create_engine, Table, Column, Integer, String, MetaData, DateTime, select
from sqlalchemy.sql import func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime

DATABASE_URL = "postgresql://postgres:admin@127.0.0.1:5433/ai_surveillance_db"

engine: Engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()
# metadata = MetaData()

class Event(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, index=True)
    event_type = Column(String, nullable=False)
    camera = Column(String, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    details = Column(String, nullable=True)

Base.metadata.create_all(engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# def log_event(event_type: str, camera: str = None, details: str = None):
#     with engine.begin() as conn:
#         conn.execute(events.insert().values(event_type=event_type, camera=camera, details=details))
