from sqlalchemy.ext.asyncio import AsyncSession
from models.audit_log import AuditLog

async def log_action(
    db: AsyncSession,
    user_id: str,
    action: str,
    details: dict | None = None
):
    log = AuditLog(
        user_id=user_id,
        action=action,
        details=details
    )

    db.add(log)

    await db.commit()
