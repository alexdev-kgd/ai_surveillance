from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from core.db import get_db
from models.permission import Permission
from models.user import User
from services.auth import get_current_user
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

    return result.scalars().all()
