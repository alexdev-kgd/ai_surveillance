from sqlalchemy import Column, String, Integer, ForeignKey, Boolean, JSON, DateTime, func
from sqlalchemy.orm import relationship
from models.base import Base

class Settings(Base):
    __tablename__ = "settings"

    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    settings = Column(JSON, nullable=False)
    updated_by = Column(String)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
