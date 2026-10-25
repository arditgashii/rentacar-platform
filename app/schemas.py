from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any

from email_validator import EmailNotValidError, validate_email
from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    PlainSerializer,
    field_validator,
)

from app.models import BookingStatus, CarStatus, Category, Feature, FuelType, Role, Transmission


def _email(value: str) -> str:
    # test_environment allows the reserved .test domain used by the seeded accounts.
    try:
        return validate_email(value, check_deliverability=False, test_environment=True).normalized.lower()
    except EmailNotValidError as error:
        raise ValueError(str(error)) from error


EmailStr = Annotated[str, Field(max_length=255), AfterValidator(_email)]

# Money is exact in Python and in the database, and a plain JSON number on the wire.
Money = Annotated[
    Decimal,
    Field(max_digits=10, decimal_places=2),
    PlainSerializer(float, return_type=float, when_used="json"),
]


def max_car_year() -> int:
    return date.today().year + 1


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


# Auth and users


class RegisterIn(Strict):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=2, max_length=120)
    phone: str = Field(default="", max_length=40)
    city: str = Field(default="", max_length=80)


class LoginIn(Strict):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    full_name: str
    phone: str
    city: str
    role: Role
    is_active: bool
    created_at: datetime


class AdminUserPatch(Strict):
    role: Role | None = None
    is_active: bool | None = None


# Cars


class CarFields(Strict):
    make: str = Field(min_length=1, max_length=60)
    model: str = Field(min_length=1, max_length=60)
    year: int = Field(ge=1990)
    category: Category
    transmission: Transmission
    fuel_type: FuelType
    seats: int = Field(ge=2, le=9)
    doors: int = Field(ge=2, le=5)
    mileage_km: int = Field(ge=0, le=2_000_000)
    color: str = Field(min_length=1, max_length=40)
    license_plate: str = Field(min_length=2, max_length=20, pattern=r"^[A-Za-z0-9 -]+$")
    daily_price: Money = Field(gt=0, le=Decimal("99999"))
    deposit: Money = Field(default=Decimal("0"), ge=0, le=Decimal("99999"))
    city: str = Field(min_length=1, max_length=80)
    pickup_address: str = Field(default="", max_length=200)
    description: str = Field(default="", max_length=2000)
    features: list[Feature] = Field(default_factory=list)
    status: CarStatus = CarStatus.AVAILABLE

    @field_validator("year")
    @classmethod
    def year_not_in_future(cls, value: int) -> int:
        if value > max_car_year():
            raise ValueError(f"must be {max_car_year()} or earlier")
        return value

    @field_validator("license_plate")
    @classmethod
    def normalize_plate(cls, value: str) -> str:
        return " ".join(value.upper().split())

    @field_validator("features")
    @classmethod
    def unique_features(cls, value: list[Feature]) -> list[Feature]:
        return list(dict.fromkeys(value))


class CarCreate(CarFields):
    pass


class CarUpdate(CarFields):
    """PUT: the full car."""


class CarPatch(Strict):
    """PATCH: only the fields that change. The merged car is validated again as a CarUpdate."""

    make: str | None = None
    model: str | None = None
    year: int | None = None
    category: Category | None = None
    transmission: Transmission | None = None
    fuel_type: FuelType | None = None
    seats: int | None = None
    doors: int | None = None
    mileage_km: int | None = None
    color: str | None = None
    license_plate: str | None = None
    daily_price: Decimal | None = None
    deposit: Decimal | None = None
    city: str | None = None
    pickup_address: str | None = None
    description: str | None = None
    features: list[Feature] | None = None
    status: CarStatus | None = None


class PhotoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    url: str
    content_type: str
    size_bytes: int
    is_primary: bool
    sort_order: int


class CarOut(BaseModel):
    id: int
    owner_id: int
    owner_name: str
    make: str
    model: str
    year: int
    category: Category
    transmission: Transmission
    fuel_type: FuelType
    seats: int
    doors: int
    mileage_km: int
    color: str
    license_plate: str
    daily_price: Money
    deposit: Money
    city: str
    pickup_address: str
    description: str
    features: list[Feature]
    status: CarStatus
    primary_photo_url: str | None
    photos: list[PhotoOut]
    created_at: datetime
    updated_at: datetime


class CarPage(BaseModel):
    items: list[CarOut]
    total: int
    page: int
    page_size: int


class DescriptionOut(BaseModel):
    description: str
    provider: str


# Bookings


class BookingIn(Strict):
    car_id: int = Field(gt=0)
    start_date: date
    end_date: date


class BookingOut(BaseModel):
    id: int
    car_id: int
    car_title: str
    client_id: int
    client_name: str
    start_date: date
    end_date: date
    days: int
    total_price: Money
    status: BookingStatus
    created_at: datetime


# Admin and notifications


class StatsOut(BaseModel):
    cars: int
    available_cars: int
    active_bookings: int
    revenue_this_month: Money
    users: int
    recent_bookings: list[BookingOut]


class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    type: str
    payload: dict[str, Any]
    created_at: datetime
