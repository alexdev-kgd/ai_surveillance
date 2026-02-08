from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, JSON
from sqlalchemy.sql import func
from models.base import Base

class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    action = Column(String, nullable=False)
    details = Column(JSON)
    created_at = Column(DateTime, server_default=func.now())
