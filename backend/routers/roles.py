from fastapi import HTTPException, APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import joinedload, selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from core.db import get_db
from core.audit_action import AuditAction
from models.user import User
from models.role import Role
from models.permission import Permission
from services.auth import get_current_user
from services.audit_log import log_action
from schemas.roles import RolePermissions, RoleSchema
from typing import List

router = APIRouter(prefix="/roles", tags=["Roles"])

@router.get("", response_model=List[RoleSchema])
async def get_roles(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if "system:configure" not in user.permissions:
        raise HTTPException(status_code=403)

    result = await db.execute(
        select(Role).options(
            selectinload(Role.permissions)
        )
    )

    roles = result.scalars().unique().all()

    return [
        RoleSchema(
            name=role.name,
            permissions=[p.name for p in role.permissions],
        )
        for role in roles
    ]

@router.put("/{role_name}/permissions")
async def update_role_permissions(
    role_name: str,
    payload: RolePermissions,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if "system:configure" not in user.permissions:
        raise HTTPException(status_code=403, detail="Forbidden")

    stmt = (
        select(Role)
        .options(joinedload(Role.permissions))
        .where(Role.name == role_name)
    )
    result = await db.execute(stmt)
    role = result.scalars().first()

    if not role:
        raise HTTPException(status_code=404, detail="Role not found")

    stmt = select(Permission).where(
        Permission.name.in_(payload.permissions)
    )
    result = await db.execute(stmt)
    permissions = result.scalars().all()

    found = {p.name for p in permissions}
    missing = set(payload.permissions) - found
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown permissions: {missing}"
        )

    role.permissions.clear()
    role.permissions.extend(permissions)

    await db.commit()

    await log_action(db, user.id, AuditAction.PERMISSION_SETTINGS_UPDATE)

    return {
        "role": role.name,
        "permissions": [p.name for p in role.permissions],
    }
