from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from core.db import get_db
from core.audit_action import AuditAction
from models.permission import Permission
from models.user import User
from services.auth import get_current_user
from services.audit_log import log_action
from typing import List

router = APIRouter(prefix="/permissions", tags=["Permissions"])

@router.get("", response_model=List[str])
async def get_all_permissions(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    if "system:configure" not in user.permissions:
        raise HTTPException(status_code=403)

    stmt = select(Permission.name)
    result = await db.execute(stmt)

    await log_action(db, user.id, AuditAction.PERMISSION_SETTINGS_ACCESS)

    return result.scalars().all()
