from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from core.db import get_db
from models.audit_log import AuditLog
from models.user import User
from models.role import Role
from services.auth import get_current_user

router = APIRouter(prefix="/audit", tags=["Audit"])

@router.get("")
async def get_audit_logs(
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    admin=Depends(get_current_user)
):
    stmt = (
        select(
            AuditLog.id,
            AuditLog.action,
            AuditLog.details,
            AuditLog.created_at,
            User.email,
            Role.name.label("role")
        )
        .join(User, User.id == AuditLog.user_id)
        .join(Role, Role.id == User.role_id)
        .order_by(desc(AuditLog.created_at))
        .limit(limit)
    )
    result = await db.execute(stmt)

    return result.mappings().all()
