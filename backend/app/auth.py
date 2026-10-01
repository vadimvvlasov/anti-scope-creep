"""Password hashing, JWT access tokens, and the current-user dependency."""

from datetime import datetime, timedelta
from functools import cache
from typing import Annotated
from uuid import UUID, uuid4

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.context import AppContext, get_context
from app.errors import AppError, ErrorCode
from app.models import UserRecord
from app.store import DuplicateEmailError, Store

TOKEN_TTL_SECONDS = 24 * 60 * 60
JWT_ALGORITHM = "HS256"

_hasher = PasswordHasher()
_bearer = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


@cache
def _dummy_hash() -> str:
    return hash_password("dummy-password-for-timing")


def create_access_token(user_id: UUID, secret: str, now: datetime) -> str:
    claims = {"sub": str(user_id), "iat": now, "exp": now + timedelta(seconds=TOKEN_TTL_SECONDS)}
    return jwt.encode(claims, secret, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str, secret: str) -> UUID | None:
    """Return the user ID from a valid, unexpired token, else None."""
    try:
        claims = jwt.decode(
            token, secret, algorithms=[JWT_ALGORITHM], options={"require": ["sub", "exp", "iat"]}
        )
        return UUID(claims["sub"])
    except (jwt.PyJWTError, ValueError):
        return None


def register_user(store: Store, email: str, password: str, now: datetime) -> UserRecord:
    user = UserRecord(id=uuid4(), email=email, password_hash=hash_password(password), created_at=now)
    try:
        store.add_user(user)
    except DuplicateEmailError:
        raise AppError(ErrorCode.EMAIL_ALREADY_EXISTS) from None
    return user


def authenticate(store: Store, email: str, password: str) -> UserRecord:
    user = store.get_user_by_email(email)
    if user is None:
        verify_password(_dummy_hash(), password)  # keep timing similar for unknown emails
        raise AppError(ErrorCode.INVALID_CREDENTIALS)
    if not verify_password(user.password_hash, password):
        raise AppError(ErrorCode.INVALID_CREDENTIALS)
    return user


def get_current_user(
    context: Annotated[AppContext, Depends(get_context)],
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> UserRecord:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise AppError(ErrorCode.UNAUTHORIZED)
    user_id = decode_access_token(credentials.credentials, context.settings.jwt_secret)
    user = context.store.get_user(user_id) if user_id else None
    if user is None:
        raise AppError(ErrorCode.UNAUTHORIZED)
    return user


CurrentUser = Annotated[UserRecord, Depends(get_current_user)]
