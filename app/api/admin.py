from fastapi import APIRouter

from app.schemas import AdminUserPatch, StatsOut, UserOut
from app.security import AdminUser, Db
from app.services import users
from app.services.stats import collect_stats

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users", response_model=list[UserOut])
async def list_users(db: Db, _: AdminUser) -> list[UserOut]:
    return [UserOut.model_validate(u) for u in await users.list_users(db)]


@router.patch("/users/{user_id}", response_model=UserOut)
async def update_user(user_id: int, data: AdminUserPatch, db: Db, admin: AdminUser) -> UserOut:
    return UserOut.model_validate(await users.update_user(db, admin, user_id, data))


@router.get("/stats", response_model=StatsOut)
async def stats(db: Db, admin: AdminUser) -> StatsOut:
    return await collect_stats(db, admin)
