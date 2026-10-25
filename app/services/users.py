import asyncio

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import AppError, not_found
from app.models import Role, User
from app.schemas import AdminUserPatch, RegisterIn
from app.security import hash_password, verify_password

# A real hash, so a login with an unknown email takes as long as one with a wrong password.
_DUMMY_HASH = hash_password("timing-equalizer")


def _email_taken() -> AppError:
    return AppError(409, "EMAIL_TAKEN", "An account with this email already exists.")


async def register(db: AsyncSession, data: RegisterIn) -> User:
    email = data.email.lower()
    if await db.scalar(select(User.id).where(User.email == email)):
        raise _email_taken()
    user = User(
        email=email,
        # bcrypt is slow on purpose; a worker thread keeps the event loop free for other requests
        password_hash=await asyncio.to_thread(hash_password, data.password),
        full_name=data.full_name,
        phone=data.phone,
        city=data.city,
        role=Role.CLIENT,
    )
    db.add(user)
    try:
        await db.commit()
    except IntegrityError as error:  # the same email registered at the same moment
        await db.rollback()
        raise _email_taken() from error
    return user


async def authenticate(db: AsyncSession, email: str, password: str) -> User:
    user = await db.scalar(select(User).where(User.email == email.lower()))
    matches = await asyncio.to_thread(verify_password, password, user.password_hash if user else _DUMMY_HASH)
    if not matches or not user:
        raise AppError(401, "INVALID_CREDENTIALS", "Wrong email or password.")
    if not user.is_active:
        raise AppError(403, "ACCOUNT_INACTIVE", "This account is deactivated.")
    return user


async def list_users(db: AsyncSession) -> list[User]:
    return list(await db.scalars(select(User).order_by(User.created_at.desc(), User.id.desc())))


async def update_user(db: AsyncSession, admin: User, user_id: int, data: AdminUserPatch) -> User:
    user = await db.get(User, user_id)
    if user is None:
        raise not_found("user")
    if user.id == admin.id and (data.is_active is False or data.role == Role.CLIENT):
        raise AppError(400, "CANNOT_CHANGE_SELF", "You cannot deactivate or demote yourself.")
    if data.role is not None:
        user.role = data.role
    if data.is_active is not None:
        user.is_active = data.is_active
    await db.commit()
    return user


async def count_users(db: AsyncSession) -> int:
    return int(await db.scalar(select(func.count(User.id))) or 0)
