"""Turns ORM objects into API shapes."""

from app.models import (
    Booking,
    BookingStatus,
    Car,
    CarPhoto,
    CarStatus,
    Category,
    Feature,
    FuelType,
    Transmission,
)
from app.schemas import BookingOut, CarOut, PhotoOut


def photo_url(photo: CarPhoto) -> str:
    return f"/media/{photo.blob_name}"


def photo_out(photo: CarPhoto) -> PhotoOut:
    return PhotoOut(
        id=photo.id,
        url=photo_url(photo),
        content_type=photo.content_type,
        size_bytes=photo.size_bytes,
        is_primary=photo.is_primary,
        sort_order=photo.sort_order,
    )


def car_out(car: Car) -> CarOut:
    primary = car.primary_photo
    photos = sorted(car.photos, key=lambda p: p.sort_order)
    return CarOut(
        id=car.id,
        owner_id=car.owner_id,
        owner_name=car.owner.full_name,
        make=car.make,
        model=car.model,
        year=car.year,
        category=Category(car.category),
        transmission=Transmission(car.transmission),
        fuel_type=FuelType(car.fuel_type),
        seats=car.seats,
        doors=car.doors,
        mileage_km=car.mileage_km,
        color=car.color,
        license_plate=car.license_plate,
        daily_price=car.daily_price,
        deposit=car.deposit,
        city=car.city,
        pickup_address=car.pickup_address,
        description=car.description,
        features=[Feature(f) for f in car.features],
        status=CarStatus(car.status),
        primary_photo_url=photo_url(primary) if primary else None,
        photos=[photo_out(p) for p in photos],
        created_at=car.created_at,
        updated_at=car.updated_at,
    )


def booking_out(booking: Booking) -> BookingOut:
    return BookingOut(
        id=booking.id,
        car_id=booking.car_id,
        car_title=f"{booking.car.year} {booking.car.make} {booking.car.model}",
        client_id=booking.client_id,
        client_name=booking.client.full_name,
        start_date=booking.start_date,
        end_date=booking.end_date,
        days=booking.days,
        total_price=booking.total_price,
        status=BookingStatus(booking.status),
        created_at=booking.created_at,
    )
