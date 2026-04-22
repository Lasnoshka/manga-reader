from typing import Optional

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthenticationError, AuthorizationError
from app.core.security import decode_access_token
from app.db.models.user import User
from app.db.session_runtime import get_db


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


async def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    if not token:
        raise AuthenticationError("Missing access token")

    payload = decode_access_token(token)
    if payload is None or "sub" not in payload:
        raise AuthenticationError("Invalid or expired token")

    try:
        user_id = int(payload["sub"])
    except (TypeError, ValueError):
        raise AuthenticationError("Invalid token subject")

    user = await db.scalar(select(User).where(User.id == user_id))
    if user is None or not user.is_active:
        raise AuthenticationError("User not found or inactive")
    return user


async def get_current_user_optional(
    token: Optional[str] = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    if not token:
        return None
    payload = decode_access_token(token)
    if payload is None or "sub" not in payload:
        return None
    try:
        user_id = int(payload["sub"])
    except (TypeError, ValueError):
        return None
    user = await db.scalar(select(User).where(User.id == user_id))
    return user if user and user.is_active else None


async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "admin":
        raise AuthorizationError("Admin role required")
    return current_user
