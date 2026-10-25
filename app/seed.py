"""Seed data: admins, clients, 24 cars with generated photos and a few bookings.

Idempotent: does nothing when the first admin already exists. Run with `python -m app.seed`.
"""

import asyncio
import io
import random
import uuid
from datetime import date, timedelta
from decimal import Decimal

from PIL import Image, ImageDraw, ImageFont
from sqlalchemy import select

from app.config import get_settings
from app.db import SessionLocal
from app.models import Booking, BookingStatus, Car, CarPhoto, CarStatus, Role, User
from app.security import hash_password
from app.storage import PhotoStorage, build_storage

ADMINS = [
    ("admin1@drivenow.test", "Arta Krasniqi"),
    ("admin2@drivenow.test", "Blerim Hoxha"),
    ("admin3@drivenow.test", "Drita Berisha"),
]
CLIENTS = [
    ("client1@drivenow.test", "Liridon Gashi", "Prishtina"),
    ("client2@drivenow.test", "Vjosa Morina", "Prizren"),
    ("client3@drivenow.test", "Arben Shala", "Peja"),
    ("client4@drivenow.test", "Teuta Kelmendi", "Gjakova"),
    ("client5@drivenow.test", "Faton Rexhepi", "Ferizaj"),
    ("client6@drivenow.test", "Elira Basha", "Tirana"),
]
INACTIVE = ("inactive@drivenow.test", "Inactive Client", "Prishtina")
CITIES = ["Prishtina", "Prizren", "Peja", "Gjakova", "Ferizaj", "Tirana"]
STREETS = [
    "Rruga Agim Ramadani 12",
    "Sheshi Shadervan 3",
    "Rruga Mbreti Bardhyl 8",
    "Rruga Nene Tereza 21",
    "Bulevardi Deshmoret 5",
    "Rruga e Kavajes 40",
]

# fmt: off
# make, model, year, category, transmission, fuel, seats, doors, price, deposit, color, features
CARS = [
    ("Volkswagen", "Golf", 2019, "compact", "manual", "diesel", 5, 5, "35.00", "200", "Grey", ["air_conditioning", "bluetooth"]),
    ("Skoda", "Octavia", 2021, "compact", "automatic", "diesel", 5, 5, "42.50", "250", "White", ["air_conditioning", "gps", "parking_sensors"]),
    ("Toyota", "Yaris", 2020, "economy", "automatic", "hybrid", 5, 5, "29.99", "150", "Red", ["air_conditioning", "bluetooth"]),
    ("Fiat", "Panda", 2018, "economy", "manual", "petrol", 4, 5, "22.00", "100", "Yellow", ["air_conditioning"]),
    ("Renault", "Clio", 2022, "economy", "manual", "petrol", 5, 5, "27.50", "120", "Blue", ["air_conditioning", "bluetooth", "rear_camera"]),
    ("Dacia", "Duster", 2021, "suv", "manual", "diesel", 5, 5, "39.00", "200", "Orange", ["air_conditioning", "roof_rack"]),
    ("Hyundai", "Tucson", 2022, "suv", "automatic", "hybrid", 5, 5, "58.00", "300", "Black", ["air_conditioning", "gps", "heated_seats", "rear_camera"]),
    ("Kia", "Sportage", 2020, "suv", "automatic", "diesel", 5, 5, "54.90", "300", "Silver", ["air_conditioning", "gps", "parking_sensors"]),
    ("BMW", "X5", 2021, "luxury", "automatic", "diesel", 5, 5, "120.00", "800", "Black", ["air_conditioning", "gps", "heated_seats", "parking_sensors", "rear_camera"]),
    ("Mercedes-Benz", "E 220", 2020, "luxury", "automatic", "diesel", 5, 4, "110.00", "700", "Silver", ["air_conditioning", "gps", "heated_seats", "bluetooth"]),
    ("Audi", "A6", 2019, "luxury", "automatic", "petrol", 5, 4, "95.00", "600", "Blue", ["air_conditioning", "gps", "bluetooth"]),
    ("Tesla", "Model 3", 2023, "electric", "automatic", "electric", 5, 4, "89.99", "500", "White", ["air_conditioning", "gps", "heated_seats", "rear_camera"]),
    ("Volkswagen", "ID.4", 2022, "electric", "automatic", "electric", 5, 5, "75.00", "400", "Grey", ["air_conditioning", "gps", "parking_sensors"]),
    ("Renault", "Zoe", 2020, "electric", "automatic", "electric", 5, 5, "45.00", "250", "Green", ["air_conditioning", "bluetooth"]),
    ("Ford", "Transit Custom", 2019, "van", "manual", "diesel", 9, 4, "70.00", "400", "White", ["air_conditioning", "roof_rack"]),
    ("Mercedes-Benz", "Vito", 2021, "van", "automatic", "diesel", 8, 4, "85.00", "500", "Black", ["air_conditioning", "gps", "child_seat"]),
    ("Opel", "Astra", 2018, "compact", "manual", "petrol", 5, 5, "30.00", "150", "Red", ["air_conditioning"]),
    ("Peugeot", "308", 2021, "compact", "automatic", "diesel", 5, 5, "40.00", "200", "Blue", ["air_conditioning", "gps", "bluetooth"]),
    ("Toyota", "RAV4", 2023, "suv", "automatic", "hybrid", 5, 5, "65.00", "350", "Grey", ["air_conditioning", "gps", "rear_camera", "child_seat"]),
    ("Seat", "Ibiza", 2019, "economy", "manual", "petrol", 5, 5, "25.00", "100", "White", ["air_conditioning", "bluetooth"]),
    ("Volvo", "XC60", 2022, "luxury", "automatic", "hybrid", 5, 5, "105.00", "650", "Dark blue", ["air_conditioning", "gps", "heated_seats", "parking_sensors"]),
    ("Nissan", "Qashqai", 2020, "suv", "manual", "petrol", 5, 5, "48.00", "250", "Red", ["air_conditioning", "gps"]),
    ("Citroen", "Berlingo", 2021, "van", "manual", "diesel", 7, 5, "52.00", "300", "Beige", ["air_conditioning", "child_seat", "roof_rack"]),
    ("Mini", "Cooper", 2019, "compact", "manual", "petrol", 4, 3, "38.00", "200", "British green", ["air_conditioning", "bluetooth"]),
]

# car index, client index, days from today, length in days, status
BOOKINGS = [
    (0, 1, -20, 4, BookingStatus.COMPLETED), (1, 2, -12, 3, BookingStatus.COMPLETED),
    (2, 3, -6, 2, BookingStatus.CANCELLED), (3, 4, -2, 5, BookingStatus.CONFIRMED),
    (4, 5, 3, 4, BookingStatus.CONFIRMED), (5, 0, 7, 3, BookingStatus.PENDING),
    (6, 1, 10, 6, BookingStatus.PENDING), (7, 2, 14, 2, BookingStatus.CONFIRMED),
    (8, 3, 20, 5, BookingStatus.PENDING), (9, 4, 25, 3, BookingStatus.CANCELLED),
]

# top and bottom colour of the photo background
PALETTE = [
    ((33, 52, 84), (89, 128, 181)), ((48, 63, 71), (128, 152, 160)), ((84, 38, 32), (190, 112, 92)),
    ((30, 70, 60), (104, 168, 140)), ((60, 50, 90), (150, 132, 196)),
]
# fmt: on


def car_photo(make: str, model: str, year: int, variant: int) -> bytes:
    """A 1200x800 JPEG: a gradient, a simple car shape and the name. No external images."""
    width, height = 1200, 800
    top, bottom = PALETTE[(sum(map(ord, make)) + variant) % len(PALETTE)]
    image = Image.new("RGB", (width, height))
    draw = ImageDraw.Draw(image)
    for y in range(height):
        t = y / height
        colour = tuple(int(a + (b - a) * t) for a, b in zip(top, bottom, strict=True))
        draw.line([(0, y), (width, y)], fill=colour)

    x = (variant - 1) * 60
    draw.rectangle([0, 620, width, height], fill=(42, 44, 48))
    body = [(220, 560), (260, 450), (420, 430), (520, 350), (780, 350), (900, 440), (1010, 460), (1010, 560)]
    draw.polygon([(px + x, py) for px, py in body], fill=(236, 238, 240))
    window = (120, 150, 175)
    draw.polygon([(540 + x, 365), (640 + x, 365), (640 + x, 440), (450 + x, 440)], fill=window)
    draw.polygon([(655 + x, 365), (770 + x, 365), (860 + x, 440), (655 + x, 440)], fill=window)
    for cx in (370 + x, 860 + x):
        draw.ellipse([cx - 70, 500, cx + 70, 640], fill=(25, 25, 28))
        draw.ellipse([cx - 32, 538, cx + 32, 602], fill=(170, 172, 176))

    # Inset from the left so the text survives the 4:3 crop on the car cards.
    draw.text((170, 90), f"{make} {model}", fill="white", font=ImageFont.load_default(size=72))
    draw.text(
        (172, 180), f"{year}  |  photo {variant}", fill=(230, 233, 238), font=ImageFont.load_default(size=40)
    )
    buffer = io.BytesIO()
    image.save(buffer, "JPEG", quality=82)
    return buffer.getvalue()


def _users(password_hash: str) -> tuple[list[User], list[User]]:
    admins = [
        User(email=email, full_name=name, password_hash=password_hash, role=Role.ADMIN, city="Prishtina")
        for email, name in ADMINS
    ]
    clients = [
        User(
            email=email,
            full_name=name,
            password_hash=password_hash,
            role=Role.CLIENT,
            city=city,
            phone=f"+383 44 {100000 + i * 1111}",
        )
        for i, (email, name, city) in enumerate(CLIENTS)
    ]
    inactive = User(
        email=INACTIVE[0],
        full_name=INACTIVE[1],
        city=INACTIVE[2],
        password_hash=password_hash,
        role=Role.CLIENT,
        is_active=False,
    )
    return [*admins, inactive], clients


def _car(i: int, owner: User, rng: random.Random) -> Car:
    make, model, year, category, transmission, fuel, seats, doors, price, deposit, color, features = CARS[i]
    city = CITIES[i % len(CITIES)]
    status = {22: CarStatus.MAINTENANCE, 23: CarStatus.DRAFT}.get(i, CarStatus.AVAILABLE)
    return Car(
        owner_id=owner.id,
        make=make,
        model=model,
        year=year,
        category=category,
        transmission=transmission,
        fuel_type=fuel,
        seats=seats,
        doors=doors,
        mileage_km=rng.randrange(8_000, 160_000, 500),
        color=color,
        license_plate=f"{(i % 7) + 1:02d}-{100 + i * 7}-{chr(65 + i % 26)}{chr(75 + i % 15)}",
        daily_price=Decimal(price),
        deposit=Decimal(deposit),
        city=city,
        pickup_address=f"{STREETS[i % len(STREETS)]}, {city}",
        description=f"Well kept {make} {model} from {year}. Clean inside, serviced on time, "
        f"easy pickup in {city}.",
        features=features,
        photos=[],
        status=status,
    )


async def seed(storage: PhotoStorage) -> bool:
    """Returns False when the data was already there."""
    # random only varies the seeded mileage, nothing security related
    rng = random.Random(42)  # nosec B311
    async with SessionLocal() as db:
        if await db.scalar(select(User.id).where(User.email == ADMINS[0][0])):
            return False

        others, clients = _users(hash_password(get_settings().seed_password))
        db.add_all([*others, *clients])
        await db.flush()

        cars: list[Car] = []
        for i in range(len(CARS)):
            car = _car(i, clients[i % len(clients)], rng)
            db.add(car)
            await db.flush()  # the car id is part of the photo blob names
            for variant in range(1, 3 + i % 3):
                blob_name = f"cars/{car.id}/{uuid.uuid4().hex}.jpg"
                data = car_photo(car.make, car.model, car.year, variant)
                await storage.upload(blob_name, data, "image/jpeg")
                car.photos.append(
                    CarPhoto(
                        blob_name=blob_name,
                        content_type="image/jpeg",
                        size_bytes=len(data),
                        is_primary=variant == 1,
                        sort_order=variant - 1,
                    )
                )
            cars.append(car)

        for car_index, client_index, offset, days, status in BOOKINGS:
            car = cars[car_index]
            client = clients[client_index]
            if client.id == car.owner_id:
                client = clients[(client_index + 1) % len(clients)]
            start = date.today() + timedelta(days=offset)
            db.add(
                Booking(
                    car_id=car.id,
                    client_id=client.id,
                    start_date=start,
                    end_date=start + timedelta(days=days),
                    days=days,
                    total_price=car.daily_price * days,
                    status=status,
                )
            )
        await db.commit()
    return True


async def main() -> None:
    storage = build_storage()
    await storage.start()
    try:
        created = await seed(storage)
    finally:
        await storage.close()
    print("Seed data created." if created else "Seed data already present, nothing to do.")


if __name__ == "__main__":
    asyncio.run(main())
