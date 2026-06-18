from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings
from app.core.exceptions import UnauthorizedException

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ── Password ─────────────────────────────────────────────────────────────────

def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


# ── JWT ───────────────────────────────────────────────────────────────────────

def _create_token(data: dict[str, Any], expires_delta: timedelta) -> str:
    payload = data.copy()
    payload["exp"] = datetime.now(timezone.utc) + expires_delta
    return jwt.encode(
        payload,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


def create_access_token(user_id: str) -> str:
    return _create_token(
        {"sub": user_id, "type": "access"},
        timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )


def create_refresh_token(user_id: str) -> str:
    return _create_token(
        {"sub": user_id, "type": "refresh"},
        timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )


def create_password_reset_token(email: str) -> str:
    """
    Short-lived, single-purpose token issued after OTP verification.
    Scoped to type='password_reset' so it cannot be used as an access
    or refresh token. TTL is 15 minutes — enough time to submit the
    new password form but short enough to limit exposure.
    """
    return _create_token(
        {"sub": email, "type": "password_reset"},
        timedelta(minutes=15),
    )


def decode_access_token(token: str) -> str:
    """Decode and validate an access token. Returns user_id."""
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        if payload.get("type") != "access":
            raise UnauthorizedException("Invalid token type")
        user_id: str | None = payload.get("sub")
        if user_id is None:
            raise UnauthorizedException("Invalid token payload")
        return user_id
    except JWTError:
        raise UnauthorizedException("Could not validate credentials")


def decode_refresh_token(token: str) -> str:
    """Decode and validate a refresh token. Returns user_id."""
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        if payload.get("type") != "refresh":
            raise UnauthorizedException("Invalid token type")
        user_id: str | None = payload.get("sub")
        if user_id is None:
            raise UnauthorizedException("Invalid token payload")
        return user_id
    except JWTError:
        raise UnauthorizedException("Could not validate credentials")


def decode_password_reset_token(token: str) -> str:
    """Decode and validate a password reset token. Returns email."""
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        if payload.get("type") != "password_reset":
            raise UnauthorizedException("Invalid token type")
        email: str | None = payload.get("sub")
        if email is None:
            raise UnauthorizedException("Invalid token payload")
        return email
    except JWTError:
        raise UnauthorizedException("Password reset token is invalid or has expired")