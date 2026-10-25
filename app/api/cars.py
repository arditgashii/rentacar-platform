from decimal import Decimal
from typing import Annotated, Literal

from fastapi import APIRouter, File, Query, Response, UploadFile

from app.deps import Storage
from app.errors import AppError
from app.llm import generate_description
from app.models import CarStatus, Category, FuelType, Transmission
from app.presenters import car_out, photo_out
from app.schemas import CarCreate, CarOut, CarPage, CarPatch, CarUpdate, DescriptionOut, PhotoOut
from app.security import CurrentUser, Db, OptionalUser
from app.services import cars, photos

router = APIRouter(prefix="/cars", tags=["cars"])


@router.get("", response_model=CarPage)
async def list_cars(
    db: Db,
    user: OptionalUser,
    q: Annotated[str | None, Query(max_length=60)] = None,
    city: Annotated[str | None, Query(max_length=80)] = None,
    category: Category | None = None,
    transmission: Transmission | None = None,
    fuel_type: FuelType | None = None,
    min_price: Annotated[Decimal | None, Query(ge=0)] = None,
    max_price: Annotated[Decimal | None, Query(ge=0)] = None,
    seats: Annotated[int | None, Query(ge=1, le=9)] = None,
    status: CarStatus | None = None,
    owner_id: Annotated[int | None, Query(gt=0)] = None,
    sort: Literal["price_asc", "price_desc", "newest"] = "newest",
    page: Annotated[int, Query(ge=1, le=10_000)] = 1,
    page_size: Annotated[int, Query(ge=1, le=cars.MAX_PAGE_SIZE)] = 12,
) -> CarPage:
    filters = cars.CarFilters(
        q=q,
        city=city,
        category=category,
        transmission=transmission,
        fuel_type=fuel_type,
        min_price=min_price,
        max_price=max_price,
        seats=seats,
        status=status,
        owner_id=owner_id,
        sort=sort,
        page=page,
        page_size=page_size,
    )
    items, total = await cars.list_cars(db, user, filters)
    return CarPage(items=[car_out(c) for c in items], total=total, page=page, page_size=page_size)


@router.post("", response_model=CarOut, status_code=201)
async def create_car(data: CarCreate, db: Db, user: CurrentUser) -> CarOut:
    return car_out(await cars.create_car(db, user, data))


@router.get("/{car_id}", response_model=CarOut)
async def get_car(car_id: int, db: Db, user: OptionalUser) -> CarOut:
    return car_out(await cars.get_car(db, user, car_id))


@router.put("/{car_id}", response_model=CarOut)
async def replace_car(car_id: int, data: CarUpdate, db: Db, user: CurrentUser) -> CarOut:
    return car_out(await cars.update_car(db, user, car_id, data))


@router.patch("/{car_id}", response_model=CarOut)
async def patch_car(car_id: int, data: CarPatch, db: Db, user: CurrentUser) -> CarOut:
    return car_out(await cars.update_car(db, user, car_id, data))


@router.delete("/{car_id}", status_code=204)
async def delete_car(car_id: int, db: Db, user: CurrentUser, storage: Storage) -> Response:
    await cars.delete_car(db, storage, user, car_id)
    return Response(status_code=204)


@router.post("/{car_id}/photos", response_model=PhotoOut, status_code=201)
async def upload_photo(
    car_id: int, db: Db, user: CurrentUser, storage: Storage, file: Annotated[UploadFile, File()]
) -> PhotoOut:
    data = await file.read(photos.MAX_BYTES + 1)
    if not data:
        raise AppError(400, "EMPTY_FILE", "The file is empty.")
    return photo_out(await photos.add_photo(db, storage, user, car_id, data))


@router.delete("/{car_id}/photos/{photo_id}", status_code=204)
async def delete_photo(car_id: int, photo_id: int, db: Db, user: CurrentUser, storage: Storage) -> Response:
    await photos.delete_photo(db, storage, user, car_id, photo_id)
    return Response(status_code=204)


@router.patch("/{car_id}/photos/{photo_id}", response_model=PhotoOut)
async def make_primary(car_id: int, photo_id: int, db: Db, user: CurrentUser) -> PhotoOut:
    return photo_out(await photos.set_primary(db, user, car_id, photo_id))


@router.post("/{car_id}/generate-description", response_model=DescriptionOut)
async def describe_car(car_id: int, db: Db, user: CurrentUser) -> DescriptionOut:
    car = await cars.get_car(db, user, car_id)
    if not cars.can_manage(user, car):
        raise AppError(403, "FORBIDDEN", "Only the owner or an admin can generate a description.")
    text, provider = await generate_description(car)
    return DescriptionOut(description=text, provider=provider)
