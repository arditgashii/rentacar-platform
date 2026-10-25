from datetime import UTC, datetime, timedelta
from typing import Annotated

import bcrypt
import jwt
from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_db
from app.errors import AppError
from app.models import Role, User
from app.secrets import get_secrets

ALGORITHM = "HS256"
COOKIE_NAME = "access_token"


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode(), password_hash.encode())


def create_token(user: User) -> str:
    expires = datetime.now(UTC) + timedelta(minutes=get_settings().jwt_expire_minutes)
    payload = {"sub": str(user.id), "role": user.role, "exp": expires}
    return jwt.encode(payload, get_secrets().get("jwt-secret"), algorithm=ALGORITHM)


def _user_id_from_token(token: str) -> int | None:
    try:
        payload = jwt.decode(token, get_secrets().get("jwt-secret"), algorithms=[ALGORITHM])
        return int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        return None


async def user_from_token(db: AsyncSession, token: str | None) -> User | None:
    """The active user the token belongs to, or None."""
    if not token:
        return None
    user_id = _user_id_from_token(token)
    if user_id is None:
        return None
    user = await db.get(User, user_id)
    return user if user and user.is_active else None


def _bearer(request: Request) -> str | None:
    scheme, _, token = request.headers.get("Authorization", "").partition(" ")
    return token if scheme.lower() == "bearer" and token else None


# The API reads only the Authorization header. The web UI reads only the cookie, so a cookie can
# never be used to call the API from another site (no CSRF on the API).


async def optional_api_user(request: Request, db: Annotated[AsyncSession, Depends(get_db)]) -> User | None:
    return await user_from_token(db, _bearer(request))


async def api_user(user: Annotated[User | None, Depends(optional_api_user)]) -> User:
    if user is None:
        raise AppError(401, "NOT_AUTHENTICATED", "Log in first.")
    return user


async def api_admin(user: Annotated[User, Depends(api_user)]) -> User:
    if user.role != Role.ADMIN:
        raise AppError(403, "ADMIN_ONLY", "Only admins can do this.")
    return user


OptionalUser = Annotated[User | None, Depends(optional_api_user)]
CurrentUser = Annotated[User, Depends(api_user)]
AdminUser = Annotated[User, Depends(api_admin)]
Db = Annotated[AsyncSession, Depends(get_db)]
