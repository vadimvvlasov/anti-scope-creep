from typing import Annotated

from fastapi import APIRouter, Depends, Request, status

from app.auth import TOKEN_TTL_SECONDS, CurrentUser, authenticate, create_access_token, register_user
from app.context import AppContext, get_context
from app.errors import AppError, ErrorCode
from app.event_limits import client_ip
from app.models import AuthResponse, LoginRequest, RegisterRequest, User, UserRecord

router = APIRouter(prefix="/auth", tags=["auth"])

Context = Annotated[AppContext, Depends(get_context)]


def to_user(record: UserRecord) -> User:
    return User(id=record.id, email=record.email, role="user", created_at=record.created_at)


def _auth_response(context: AppContext, user: UserRecord) -> AuthResponse:
    token = create_access_token(user.id, context.settings.jwt_secret, context.clock())
    return AuthResponse(access_token=token, token_type="bearer", expires_in=TOKEN_TTL_SECONDS, user=to_user(user))


@router.post("/register", status_code=status.HTTP_201_CREATED, response_model=AuthResponse)
def register(body: RegisterRequest, request: Request, context: Context) -> AuthResponse:
    ip, now, limiter = client_ip(request), context.clock(), context.auth_limiter
    if not limiter.register_allowed(ip, now):
        raise AppError(ErrorCode.TOO_MANY_ATTEMPTS)
    limiter.register_ip.add(ip, now)
    user = register_user(context.store, body.email, body.password, now)
    return _auth_response(context, user)


@router.post("/login", response_model=AuthResponse)
def login(body: LoginRequest, request: Request, context: Context) -> AuthResponse:
    ip, now, limiter = client_ip(request), context.clock(), context.auth_limiter
    if not limiter.login_allowed(ip, body.email, now):
        raise AppError(ErrorCode.TOO_MANY_ATTEMPTS)
    limiter.login_ip.add(ip, now)
    try:
        user = authenticate(context.store, body.email, body.password)
    except AppError:
        limiter.login_email.add(body.email, now)
        raise
    return _auth_response(context, user)


@router.get("/me", response_model=User)
def me(user: CurrentUser) -> User:
    return to_user(user)
