from sqlalchemy import Column, Integer, String, DateTime
from datetime import datetime
from models.base import Base

class Event(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, index=True)
    event_type = Column(String, nullable=False)
    camera = Column(String, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    details = Column(String, nullable=True)
