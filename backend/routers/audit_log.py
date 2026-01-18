from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, and_,  or_, cast, String
from datetime import datetime, timedelta
from typing import Optional

from core.db import get_db
from core.mappings import ROLE_LABELS, ROLE_LABELS_REVERSE, ACTION_LABELS, ACTION_LABELS_REVERSE
from models.audit_log import AuditLog
from models.user import User
from models.role import Role
from services.auth import get_current_user
from schemas.audit import AuditLogPage
from utils.convert_to_naive_utc import convert_to_naive_utc

router = APIRouter(prefix="/audit", tags=["Audit"])

@router.get("", response_model=AuditLogPage)
async def get_audit_logs(
    page: int = Query(0, ge=0),
    size: int = Query(10, le=100),
    search: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    role: Optional[str] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    admin=Depends(get_current_user)
):
    filters = []

    if action:
        filters.append(AuditLog.action == action)

    if role:
        filters.append(Role.name == role)

    if date_from:
        date_from = convert_to_naive_utc(date_from)
        filters.append(AuditLog.created_at >= date_from)

    if date_to:
        date_to = convert_to_naive_utc(date_to)
        filters.append(AuditLog.created_at <= date_to)

    if search:
        search_normalized = search.lower()
        mapped_roles = [r for k, r in ROLE_LABELS_REVERSE.items() if search_normalized in k]
        mapped_actions = [a for k, a in ACTION_LABELS_REVERSE.items() if search_normalized in k]

        filters.append(
            or_(
                User.email.ilike(f"%{search}%"),
                AuditLog.action.in_(mapped_actions) if mapped_actions else False,
                User.role.has(Role.name.in_(mapped_roles)) if mapped_roles else False
            )
        )

    base_stmt = (
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
        .where(and_(*filters))
    )

    total_stmt = select(func.count()).select_from(base_stmt.subquery())
    total = (await db.execute(total_stmt)).scalar()

    stmt = (
        base_stmt
        .order_by(desc(AuditLog.created_at))
        .offset(page * size)
        .limit(size)
    )

    result = await db.execute(stmt)

    return {
        "items": result.mappings().all(),
        "total": total,
        "page": page,
        "size": size,
    }
