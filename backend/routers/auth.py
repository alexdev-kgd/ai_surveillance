from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from models.user import User
from core.db import get_db
from schemas.auth import LoginRequest
from services.auth import (
    register_user,
    authenticate_user,
    get_current_user
)

router = APIRouter(prefix="/auth", tags=["Auth"])

@router.post("/register")
async def register(
    data,
    db: AsyncSession = Depends(get_db),
):
    await register_user(
        db=db,
        email=data.email,
        password=data.password,
    )

    return {"status": "registered"}

@router.post("/login")
async def login(
    data: LoginRequest,
    db: AsyncSession = Depends(get_db),
):
    token = await authenticate_user(
        db=db,
        email=data.email,
        password=data.password,
    )

    return {
        "access_token": token,
        "token_type": "bearer",
    }

@router.get("/me")
async def me(user: User = Depends(get_current_user)):
    return {
        "id": user.id,
        "email": user.email,
        "role": user.role.name,
        "permissions": [p.name for p in user.role.permissions],
    }
