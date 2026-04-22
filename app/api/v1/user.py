from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr, Field, ConfigDict
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.exceptions import (
    AuthenticationError,
    BadRequestError,
    ResourceAlreadyExistsError,
)
from app.core.logger import log_api_call
from app.core.security import create_access_token, hash_password, verify_password
from app.db.models.user import User
from app.db.session_runtime import get_db


router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class UpdateProfileRequest(BaseModel):
    email: Optional[EmailStr] = None
    avatar_url: Optional[str] = Field(default=None, max_length=500)
    password: Optional[str] = Field(default=None, min_length=8, max_length=128)


class UserResponse(BaseModel):
    id: int
    username: str
    email: EmailStr
    role: str
    is_active: bool
    avatar_url: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


@router.post("/register", response_model=TokenResponse, status_code=201)
@log_api_call
async def register(payload: RegisterRequest, db: AsyncSession = Depends(get_db)):
    existing = await db.scalar(
        select(User).where(or_(User.username == payload.username, User.email == payload.email))
    )
    if existing is not None:
        identifier = "username" if existing.username == payload.username else "email"
        raise ResourceAlreadyExistsError(resource="User", identifier=identifier)

    user = User(
        username=payload.username,
        email=payload.email,
        password_hash=hash_password(payload.password),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    token = create_access_token(user.id)
    return TokenResponse(access_token=token, user=UserResponse.model_validate(user))


@router.post("/login", response_model=TokenResponse)
@log_api_call
async def login(
    form: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    user = await db.scalar(
        select(User).where(or_(User.username == form.username, User.email == form.username))
    )
    if user is None or not verify_password(form.password, user.password_hash):
        raise AuthenticationError("Invalid username or password")
    if not user.is_active:
        raise AuthenticationError("User is disabled")

    token = create_access_token(user.id)
    return TokenResponse(access_token=token, user=UserResponse.model_validate(user))


@router.get("/me", response_model=UserResponse)
@log_api_call
async def me(current_user: User = Depends(get_current_user)):
    return current_user


@router.patch("/me", response_model=UserResponse)
@log_api_call
async def update_me(
    payload: UpdateProfileRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    data = payload.model_dump(exclude_unset=True)
    if not data:
        raise BadRequestError("No fields to update")

    if "email" in data and data["email"] != current_user.email:
        clash = await db.scalar(
            select(User).where(User.email == data["email"], User.id != current_user.id)
        )
        if clash is not None:
            raise ResourceAlreadyExistsError(resource="User", identifier="email")
        current_user.email = data["email"]

    if "avatar_url" in data:
        current_user.avatar_url = data["avatar_url"]

    if "password" in data and data["password"]:
        current_user.password_hash = hash_password(data["password"])

    await db.commit()
    await db.refresh(current_user)
    return current_user
