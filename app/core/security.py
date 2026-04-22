from datetime import timedelta
from typing import Any, Optional

import bcrypt
from jose import JWTError, jwt

from app.config import settings
from app.core.datetime_utils import utcnow


_BCRYPT_MAX_BYTES = 72


def _encode_password(password: str) -> bytes:
    """bcrypt has a hard 72-byte input limit; truncate predictably."""
    return password.encode("utf-8")[:_BCRYPT_MAX_BYTES]


def hash_password(password: str) -> str:
    return bcrypt.hashpw(_encode_password(password), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(_encode_password(plain), hashed.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(subject: str | int, expires_minutes: Optional[int] = None) -> str:
    expire = utcnow() + timedelta(
        minutes=expires_minutes or settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    payload: dict[str, Any] = {"sub": str(subject), "exp": expire, "iat": utcnow()}
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> Optional[dict[str, Any]]:
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    except JWTError:
        return None
