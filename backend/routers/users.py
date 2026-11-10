from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.audit_action import AuditAction
from core.db import get_db
from models.audit_log import AuditLog
from models.role import Role
from models.user import User
from schemas.users import UserCreate, UserOut, UserUpdate
from services.audit_log import log_action
from services.auth import get_current_user, hash_password

router = APIRouter(prefix="/users", tags=["Users"])


def require_user_permission(user: User, permission: str) -> None:
    if permission not in user.permissions:
        raise HTTPException(status_code=403, detail="Недостаточно прав")


def clean_login(login: str) -> str:
    value = login.strip()
    if not value:
        raise HTTPException(status_code=422, detail="Укажите логин")
    return value


def clean_password(password: str) -> str:
    value = password.strip()
    if not value:
        raise HTTPException(status_code=422, detail="Укажите пароль")
    if len(value.encode("utf-8")) > 72:
        raise HTTPException(status_code=422, detail="Пароль слишком длинный")
    return value


async def get_role_by_name(db: AsyncSession, name: str) -> Role:
    role = (
        await db.execute(select(Role).where(Role.name == name.strip()))
    ).scalar_one_or_none()
    if role is None:
        raise HTTPException(status_code=400, detail="Роль не найдена")
    return role


async def count_admins(db: AsyncSession) -> int:
    result = await db.execute(
        select(func.count(User.id))
        .join(Role, User.role_id == Role.id)
        .where(Role.name == "ADMIN")
    )
    return int(result.scalar_one())


def to_user_out(user: User) -> UserOut:
    role_name = user.role.name if user.role else ""
    return UserOut(id=user.id, login=user.login, role=role_name)


async def get_user_or_404(db: AsyncSession, user_id: int) -> User:
    result = await db.execute(
        select(User).options(selectinload(User.role)).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    return user


@router.get("", response_model=list[UserOut])
async def list_users(
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    require_user_permission(actor, "users:read")

    result = await db.execute(
        select(User).options(selectinload(User.role)).order_by(User.id)
    )
    payload = [to_user_out(user) for user in result.scalars().all()]

    await log_action(db, actor.id, AuditAction.USER_LIST_ACCESS)
    return payload


@router.post("", response_model=UserOut)
async def create_user(
    payload: UserCreate,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    require_user_permission(actor, "users:write")

    login = clean_login(payload.login)
    password = clean_password(payload.password)
    role = await get_role_by_name(db, payload.role)

    existing = (
        await db.execute(select(User).where(User.login == login))
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=409,
            detail="Пользователь с таким логином уже существует",
        )

    user = User(
        login=login,
        password_hash=hash_password(password),
        role=role,
    )
    db.add(user)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Пользователь с таким логином уже существует",
        )

    await log_action(
        db,
        actor.id,
        AuditAction.USER_ADDED,
        details={"message": f'Пользователь "{login}" добавлен'},
    )
    return UserOut(id=user.id, login=login, role=role.name)


@router.patch("/{user_id}", response_model=UserOut)
async def update_user(
    user_id: int,
    payload: UserUpdate,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    require_user_permission(actor, "users:write")

    target = await get_user_or_404(db, user_id)
    login = clean_login(payload.login)
    role = await get_role_by_name(db, payload.role)

    if target.id == actor.id and login != actor.login:
        raise HTTPException(status_code=400, detail="Нельзя изменить собственный логин")

    if target.role and target.role.name == "ADMIN" and role.name != "ADMIN":
        if await count_admins(db) <= 1:
            raise HTTPException(
                status_code=400,
                detail="Нельзя убрать последнего администратора",
            )

    existing = (
        await db.execute(
            select(User).where(User.login == login, User.id != target.id)
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=409,
            detail="Пользователь с таким логином уже существует",
        )

    target.login = login
    target.role = role
    if payload.password is not None and payload.password.strip():
        target.password_hash = hash_password(clean_password(payload.password))

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Пользователь с таким логином уже существует",
        )

    await log_action(
        db,
        actor.id,
        AuditAction.USER_UPDATED,
        details={"message": f'Пользователь "{login}" изменён'},
    )
    return UserOut(id=target.id, login=login, role=role.name)


@router.delete("/{user_id}")
async def delete_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    require_user_permission(actor, "users:write")

    target = await get_user_or_404(db, user_id)
    if target.id == actor.id:
        raise HTTPException(status_code=400, detail="Нельзя удалить свою учётную запись")

    if target.role and target.role.name == "ADMIN" and await count_admins(db) <= 1:
        raise HTTPException(
            status_code=400,
            detail="Нельзя удалить последнего администратора",
        )

    login = target.login
    await db.execute(
        update(AuditLog).where(AuditLog.user_id == target.id).values(user_id=None)
    )
    await db.delete(target)
    await db.commit()

    await log_action(
        db,
        actor.id,
        AuditAction.USER_DELETED,
        details={"message": f'Пользователь "{login}" удалён'},
    )
    return {"status": "deleted"}
