from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr, Field, ConfigDict, field_validator, model_validator
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.exceptions import (
    AuthenticationError,
    BadRequestError,
    ResourceAlreadyExistsError,
)
from app.core.logger import log_api_call
from app.core.password_policy import (
    ensure_password_differs_from_username,
    validate_password_strength,
)
from app.core.rate_limit import RateLimiter
from app.core.security import create_access_token, hash_password, verify_password
from app.db.models.user import User
from app.db.session_runtime import get_db


router = APIRouter(prefix="/auth", tags=["auth"])

_register_limiter = RateLimiter(key="auth:register", max_requests=5, window_seconds=60)
_login_limiter = RateLimiter(key="auth:login", max_requests=10, window_seconds=60)


class RegisterRequest(BaseModel):
    username: str = Field(
        min_length=3,
        max_length=64,
        description="Unique handle, 3–64 chars, used as login.",
        examples=["alice"],
    )
    email: EmailStr = Field(
        description="Unique email address, used for login and recovery.",
        examples=["alice@example.com"],
    )
    password: str = Field(
        min_length=8,
        max_length=128,
        description=(
            "8–128 chars; must not be a common breached password, must have "
            "at least 4 unique characters, and must differ from the username."
        ),
        examples=["tr0ub4dor&3"],
    )

    @field_validator("password")
    @classmethod
    def _check_password_strength(cls, v: str) -> str:
        return validate_password_strength(v)

    @model_validator(mode="after")
    def _check_password_not_username(self):
        ensure_password_differs_from_username(self.password, self.username)
        return self


class UpdateProfileRequest(BaseModel):
    email: Optional[EmailStr] = Field(
        default=None,
        description="New email; must remain unique across users.",
        examples=["alice.new@example.com"],
    )
    avatar_url: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Absolute URL to an avatar image, up to 500 chars.",
        examples=["https://cdn.example.com/avatars/alice.png"],
    )
    password: Optional[str] = Field(
        default=None,
        min_length=8,
        max_length=128,
        description="New password; same strength rules as on register.",
        examples=["n3wp4ssw0rd!"],
    )

    @field_validator("password")
    @classmethod
    def _check_password_strength(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        return validate_password_strength(v)


class UserResponse(BaseModel):
    id: int = Field(description="User primary key.", examples=[42])
    username: str = Field(description="Unique handle.", examples=["alice"])
    email: EmailStr = Field(examples=["alice@example.com"])
    role: str = Field(
        description='Either "user" or "admin".', examples=["user"]
    )
    is_active: bool = Field(
        description="False if the account has been disabled by an admin.",
        examples=[True],
    )
    avatar_url: Optional[str] = Field(default=None, examples=[None])
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TokenResponse(BaseModel):
    access_token: str = Field(
        description="JWT access token; pass as 'Authorization: Bearer <token>'.",
        examples=["eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."],
    )
    token_type: str = Field(default="bearer", examples=["bearer"])
    user: UserResponse


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=201,
    dependencies=[Depends(_register_limiter)],
)
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


@router.post(
    "/login",
    response_model=TokenResponse,
    dependencies=[Depends(_login_limiter)],
)
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
