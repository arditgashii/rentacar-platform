from dataclasses import dataclass
from decimal import ROUND_DOWN, Decimal
from typing import Any

from pydantic import ValidationError
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.errors import AppError, forbidden, not_found
from app.models import Car, CarStatus, Role, User
from app.schemas import CarCreate, CarPatch, CarUpdate
from app.storage import PhotoStorage

SORTS: dict[str, tuple[Any, ...]] = {
    "price_asc": (Car.daily_price.asc(), Car.id.asc()),
    "price_desc": (Car.daily_price.desc(), Car.id.desc()),
    "newest": (Car.created_at.desc(), Car.id.desc()),
}
MAX_PAGE_SIZE = 50


@dataclass
class CarFilters:
    q: str | None = None
    city: str | None = None
    category: str | None = None
    transmission: str | None = None
    fuel_type: str | None = None
    min_price: Decimal | None = None
    max_price: Decimal | None = None
    seats: int | None = None
    status: str | None = None
    owner_id: int | None = None
    sort: str = "newest"
    page: int = 1
    page_size: int = 12


def can_manage(user: User | None, car: Car) -> bool:
    return user is not None and (user.role == Role.ADMIN or car.owner_id == user.id)


async def list_cars(db: AsyncSession, user: User | None, f: CarFilters) -> tuple[list[Car], int]:
    """Public visitors see only available cars; admins and owners (with owner_id) see every status."""
    query = select(Car)
    sees_all = user is not None and (user.role == Role.ADMIN or f.owner_id == user.id)
    if not sees_all:
        query = query.where(Car.status == CarStatus.AVAILABLE)
    elif f.status:
        query = query.where(Car.status == f.status)

    if f.q:
        like = f"%{f.q.strip()}%"
        query = query.where(or_(Car.make.ilike(like), Car.model.ilike(like)))
    if f.city:
        query = query.where(Car.city.ilike(f.city.strip()))
    if f.category:
        query = query.where(Car.category == f.category)
    if f.transmission:
        query = query.where(Car.transmission == f.transmission)
    if f.fuel_type:
        query = query.where(Car.fuel_type == f.fuel_type)
    if f.min_price is not None:
        query = query.where(Car.daily_price >= f.min_price)
    if f.max_price is not None:
        if get_settings().bugs_on:
            # BUG-004: the upper bound is exclusive, so a car priced exactly at max_price is missing.
            query = query.where(Car.daily_price < f.max_price)
        else:
            query = query.where(Car.daily_price <= f.max_price)
    if f.seats is not None:
        query = query.where(Car.seats >= f.seats)
    if f.owner_id is not None:
        query = query.where(Car.owner_id == f.owner_id)

    total = int(await db.scalar(select(func.count()).select_from(query.subquery())) or 0)
    query = query.order_by(*SORTS.get(f.sort, SORTS["newest"]))
    query = query.offset((f.page - 1) * f.page_size).limit(f.page_size)
    return list((await db.scalars(query)).unique()), total


async def get_car(db: AsyncSession, user: User | None, car_id: int) -> Car:
    """A car that is not available is visible only to its owner and to admins."""
    car = await db.get(Car, car_id)
    if car is None or (car.status != CarStatus.AVAILABLE and not can_manage(user, car)):
        raise not_found("car")
    return car


async def _get_managed_car(db: AsyncSession, user: User, car_id: int) -> Car:
    car = await db.get(Car, car_id)
    if car is None:
        raise not_found("car")
    if not can_manage(user, car):
        raise forbidden("Only the owner or an admin can change this car.")
    return car


async def _commit_car(db: AsyncSession, car: Car) -> Car:
    try:
        await db.commit()
    except IntegrityError as error:
        await db.rollback()
        raise AppError(409, "PLATE_TAKEN", "A car with this license plate already exists.") from error
    await db.refresh(car)
    return car


async def create_car(db: AsyncSession, user: User, data: CarCreate) -> Car:
    car = Car(owner_id=user.id, **data.model_dump())
    db.add(car)
    return await _commit_car(db, car)


def _car_fields(car: Car) -> dict[str, Any]:
    return {name: getattr(car, name) for name in CarUpdate.model_fields}


async def update_car(db: AsyncSession, user: User, car_id: int, data: CarUpdate | CarPatch) -> Car:
    car = await _get_managed_car(db, user, car_id)
    if isinstance(data, CarPatch):
        try:
            data = CarUpdate.model_validate({**_car_fields(car), **data.model_dump(exclude_unset=True)})
        except ValidationError as error:
            problems = "; ".join(f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in error.errors())
            raise AppError(422, "VALIDATION_ERROR", problems) from error

    values = data.model_dump()
    if get_settings().bugs_on:
        # BUG-001: the price is cut to a whole number when a car is updated (89.99 becomes 89.00).
        values["daily_price"] = values["daily_price"].quantize(Decimal("1"), rounding=ROUND_DOWN)
    for name, value in values.items():
        setattr(car, name, value)
    return await _commit_car(db, car)


async def delete_car(db: AsyncSession, storage: PhotoStorage, user: User, car_id: int) -> None:
    if get_settings().bugs_on:
        # BUG-003: only checks that someone is logged in, not that they own the car.
        car = await db.get(Car, car_id)
        if car is None:
            raise not_found("car")
    else:
        car = await _get_managed_car(db, user, car_id)
    blob_names = [photo.blob_name for photo in car.photos]
    await db.delete(car)
    await db.commit()
    for name in blob_names:
        await storage.delete(name)


async def count_cars(db: AsyncSession, status: str | None = None) -> int:
    query = select(func.count(Car.id))
    if status:
        query = query.where(Car.status == status)
    return int(await db.scalar(query) or 0)
