from datetime import UTC, date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from sqlalchemy import JSON, Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class Role(StrEnum):
    ADMIN = "admin"
    CLIENT = "client"


class Category(StrEnum):
    ECONOMY = "economy"
    COMPACT = "compact"
    SUV = "suv"
    VAN = "van"
    LUXURY = "luxury"
    ELECTRIC = "electric"


class Transmission(StrEnum):
    MANUAL = "manual"
    AUTOMATIC = "automatic"


class FuelType(StrEnum):
    PETROL = "petrol"
    DIESEL = "diesel"
    HYBRID = "hybrid"
    ELECTRIC = "electric"


class CarStatus(StrEnum):
    DRAFT = "draft"
    AVAILABLE = "available"
    MAINTENANCE = "maintenance"
    ARCHIVED = "archived"


class Feature(StrEnum):
    AIR_CONDITIONING = "air_conditioning"
    GPS = "gps"
    BLUETOOTH = "bluetooth"
    CHILD_SEAT = "child_seat"
    HEATED_SEATS = "heated_seats"
    PARKING_SENSORS = "parking_sensors"
    REAR_CAMERA = "rear_camera"
    ROOF_RACK = "roof_rack"


class BookingStatus(StrEnum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(100))
    full_name: Mapped[str] = mapped_column(String(120))
    phone: Mapped[str] = mapped_column(String(40), default="")
    city: Mapped[str] = mapped_column(String(80), default="")
    role: Mapped[str] = mapped_column(String(20), default=Role.CLIENT)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Car(Base):
    __tablename__ = "cars"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    make: Mapped[str] = mapped_column(String(60))
    model: Mapped[str] = mapped_column(String(60))
    year: Mapped[int] = mapped_column(Integer)
    category: Mapped[str] = mapped_column(String(20), index=True)
    transmission: Mapped[str] = mapped_column(String(20))
    fuel_type: Mapped[str] = mapped_column(String(20))
    seats: Mapped[int] = mapped_column(Integer)
    doors: Mapped[int] = mapped_column(Integer)
    mileage_km: Mapped[int] = mapped_column(Integer)
    color: Mapped[str] = mapped_column(String(40))
    license_plate: Mapped[str] = mapped_column(String(20), unique=True)
    daily_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), index=True)
    deposit: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0"))
    city: Mapped[str] = mapped_column(String(80), index=True)
    pickup_address: Mapped[str] = mapped_column(String(200), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    features: Mapped[list[str]] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(20), default=CarStatus.AVAILABLE, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    owner: Mapped[User] = relationship(lazy="joined")
    photos: Mapped[list["CarPhoto"]] = relationship(
        back_populates="car",
        cascade="all, delete-orphan",
        order_by="CarPhoto.sort_order",
        lazy="selectin",
    )

    @property
    def primary_photo(self) -> "CarPhoto | None":
        return next((p for p in self.photos if p.is_primary), self.photos[0] if self.photos else None)


class CarPhoto(Base):
    __tablename__ = "car_photos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    car_id: Mapped[int] = mapped_column(ForeignKey("cars.id", ondelete="CASCADE"), index=True)
    blob_name: Mapped[str] = mapped_column(String(200), unique=True)
    content_type: Mapped[str] = mapped_column(String(40))
    size_bytes: Mapped[int] = mapped_column(Integer)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    car: Mapped[Car] = relationship(back_populates="photos")


class Booking(Base):
    __tablename__ = "bookings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    car_id: Mapped[int] = mapped_column(ForeignKey("cars.id", ondelete="CASCADE"), index=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    days: Mapped[int] = mapped_column(Integer)
    total_price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    status: Mapped[str] = mapped_column(String(20), default=BookingStatus.PENDING, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    car: Mapped[Car] = relationship(lazy="joined")
    client: Mapped[User] = relationship(lazy="joined")


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    type: Mapped[str] = mapped_column(String(60))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
