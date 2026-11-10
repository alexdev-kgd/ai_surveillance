from pydantic import BaseModel
from datetime import datetime
from typing import Optional, Any

class AuditLogOut(BaseModel):
    id: int
    action: str
    details: Optional[Any]
    created_at: datetime
    userId: Optional[int] = None
    role: Optional[str] = None

class AuditLogPage(BaseModel):
    items: list[AuditLogOut]
    total: int
    page: int
    size: int
