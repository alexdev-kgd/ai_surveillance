import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select
from models.base import Base
from models.user import User
from models.role import Role
from models.settings import Settings
from models.audit_log import AuditLog
from models.permission import Permission, role_permissions
from passlib.context import CryptContext
from core.config import DEFAULT_SETTINGS, PERMISSIONS
from core.db import DATABASE_URL, engine, AsyncSessionLocal as async_session

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

async def create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def init_data():
    async with async_session() as session:
        # Settings
        res = await session.execute(select(Settings).where(Settings.name == "default"))
        settings = res.scalar_one_or_none()
        if not settings:
            settings = Settings(
                name="default",
                settings=DEFAULT_SETTINGS,
                updated_by="system"
            )
            session.add(settings)

        # Permissions
        perms = []
        for name in PERMISSIONS:
            res = await session.execute(select(Permission).where(Permission.name == name))
            p = res.scalar_one_or_none()
            if not p:
                p = Permission(name=name)
                session.add(p)
            perms.append(p)

        await session.commit()

        # Roles
        res = await session.execute(select(Role).where(Role.name == "ADMIN"))
        admin_role = res.scalar_one_or_none()
        if not admin_role:
            admin_role = Role(name="ADMIN", permissions=perms)
            session.add(admin_role)

        res = await session.execute(select(Role).where(Role.name == "OPERATOR"))
        operator_role = res.scalar_one_or_none()
        if not operator_role:
            operator_perms = [p for p in perms if "read" in p.name]  # Read-only permissions
            operator_role = Role(name="OPERATOR", permissions=operator_perms)
            session.add(operator_role)

        await session.commit()

        def hash_password(password: str) -> str:
            return pwd_context.hash(password)

        # admin
        res = await session.execute(select(User).where(User.email == "admin@test.com"))
        if not res.scalar_one_or_none():
            user_admin = User(
                email="admin@test.com",
                password_hash=hash_password("1234"),
                role=admin_role
            )
            session.add(user_admin)

        # operator
        res = await session.execute(select(User).where(User.email == "operator@test.com"))
        if not res.scalar_one_or_none():
            user_operator = User(
                email="operator@test.com",
                password_hash=hash_password("1234"),
                role=operator_role
            )
            session.add(user_operator)

        await session.commit()
        print("Таблицы созданы. Права, роли и тестовые пользователи добавлены.")

async def main():
    await create_tables()
    await init_data()
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())
