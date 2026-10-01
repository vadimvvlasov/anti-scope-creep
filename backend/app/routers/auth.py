from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.auth import TOKEN_TTL_SECONDS, CurrentUser, authenticate, create_access_token, register_user
from app.context import AppContext, get_context
from app.models import AuthResponse, LoginRequest, RegisterRequest, User, UserRecord

router = APIRouter(prefix="/auth", tags=["auth"])

Context = Annotated[AppContext, Depends(get_context)]


def to_user(record: UserRecord) -> User:
    return User(id=record.id, email=record.email, role="user", created_at=record.created_at)


def _auth_response(context: AppContext, user: UserRecord) -> AuthResponse:
    token = create_access_token(user.id, context.settings.jwt_secret, context.clock())
    return AuthResponse(access_token=token, expires_in=TOKEN_TTL_SECONDS, user=to_user(user))


@router.post("/register", status_code=status.HTTP_201_CREATED, response_model=AuthResponse)
def register(body: RegisterRequest, context: Context) -> AuthResponse:
    user = register_user(context.store, body.email, body.password, context.clock())
    return _auth_response(context, user)


@router.post("/login", response_model=AuthResponse)
def login(body: LoginRequest, context: Context) -> AuthResponse:
    user = authenticate(context.store, body.email, body.password)
    return _auth_response(context, user)


@router.get("/me", response_model=User)
def me(user: CurrentUser) -> User:
    return to_user(user)
