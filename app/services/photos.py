import asyncio
import io
import uuid

from PIL import Image, UnidentifiedImageError
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import AppError, forbidden, not_found
from app.models import Car, CarPhoto, User
from app.services.cars import can_manage
from app.storage import PhotoStorage

MAX_PHOTOS = 8
MAX_BYTES = 5 * 1024 * 1024
# Pillow format name -> (content type, file extension). The content is checked, not the file name.
ALLOWED_FORMATS = {
    "JPEG": ("image/jpeg", "jpg"),
    "PNG": ("image/png", "png"),
    "WEBP": ("image/webp", "webp"),
}


def detect_image(data: bytes) -> tuple[str, str]:
    try:
        with Image.open(io.BytesIO(data)) as image:
            image.verify()
            image_format = image.format or ""
    except (UnidentifiedImageError, OSError, SyntaxError) as error:
        raise AppError(400, "INVALID_IMAGE", "The file is not a readable image.") from error
    if image_format not in ALLOWED_FORMATS:
        raise AppError(400, "UNSUPPORTED_IMAGE", "Only JPG, PNG and WEBP photos are allowed.")
    return ALLOWED_FORMATS[image_format]


async def _managed_car(db: AsyncSession, user: User, car_id: int) -> Car:
    car = await db.get(Car, car_id)
    if car is None:
        raise not_found("car")
    if not can_manage(user, car):
        raise forbidden("Only the owner or an admin can change the photos of this car.")
    return car


async def add_photo(
    db: AsyncSession, storage: PhotoStorage, user: User, car_id: int, data: bytes
) -> CarPhoto:
    car = await _managed_car(db, user, car_id)
    if len(car.photos) >= MAX_PHOTOS:
        raise AppError(409, "TOO_MANY_PHOTOS", f"A car can have at most {MAX_PHOTOS} photos.")
    if len(data) > MAX_BYTES:
        raise AppError(413, "PHOTO_TOO_LARGE", "A photo can be at most 5 MB.")
    content_type, extension = await asyncio.to_thread(detect_image, data)

    blob_name = f"cars/{car.id}/{uuid.uuid4().hex}.{extension}"
    await storage.upload(blob_name, data, content_type)
    photo = CarPhoto(
        blob_name=blob_name,
        content_type=content_type,
        size_bytes=len(data),
        is_primary=not car.photos,
        sort_order=max((p.sort_order for p in car.photos), default=-1) + 1,
    )
    car.photos.append(photo)
    try:
        await db.commit()
    except Exception:
        await storage.delete(blob_name)
        raise
    return photo


def _find_photo(car: Car, photo_id: int) -> CarPhoto:
    photo = next((p for p in car.photos if p.id == photo_id), None)
    if photo is None:
        raise not_found("photo")
    return photo


async def delete_photo(
    db: AsyncSession, storage: PhotoStorage, user: User, car_id: int, photo_id: int
) -> None:
    car = await _managed_car(db, user, car_id)
    photo = _find_photo(car, photo_id)
    car.photos.remove(photo)
    if photo.is_primary and car.photos:
        car.photos[0].is_primary = True
    await db.commit()
    await storage.delete(photo.blob_name)


async def set_primary(db: AsyncSession, user: User, car_id: int, photo_id: int) -> CarPhoto:
    car = await _managed_car(db, user, car_id)
    chosen = _find_photo(car, photo_id)
    for photo in car.photos:
        photo.is_primary = photo is chosen
    await db.commit()
    return chosen


async def move_photo(db: AsyncSession, user: User, car_id: int, photo_id: int, direction: int) -> None:
    """Swaps a photo with its neighbour; direction is -1 (earlier) or 1 (later)."""
    car = await _managed_car(db, user, car_id)
    photos = sorted(car.photos, key=lambda p: p.sort_order)
    index = photos.index(_find_photo(car, photo_id))
    other = index + direction
    if 0 <= other < len(photos):
        photos[index].sort_order, photos[other].sort_order = (
            photos[other].sort_order,
            photos[index].sort_order,
        )
        await db.commit()
