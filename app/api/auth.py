from fastapi import APIRouter

from app.schemas import LoginIn, RegisterIn, TokenOut, UserOut
from app.security import CurrentUser, Db, create_token
from app.services import users

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserOut, status_code=201)
async def register(data: RegisterIn, db: Db) -> UserOut:
    return UserOut.model_validate(await users.register(db, data))


@router.post("/login", response_model=TokenOut)
async def login(data: LoginIn, db: Db) -> TokenOut:
    user = await users.authenticate(db, data.email, data.password)
    return TokenOut(access_token=create_token(user))


@router.get("/me", response_model=UserOut)
async def me(user: CurrentUser) -> UserOut:
    return UserOut.model_validate(user)
