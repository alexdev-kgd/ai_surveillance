from sqlalchemy import create_engine, Table, Column, Integer, String, MetaData, DateTime, select
from sqlalchemy.sql import func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime

DATABASE_URL = "postgresql+asyncpg://postgres:admin@127.0.0.1:5433/ai_surveillance_db"

engine = create_async_engine(DATABASE_URL)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
Base = declarative_base()

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
