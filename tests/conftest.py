import io
import os
import tempfile
from collections.abc import AsyncIterator
from pathlib import Path

# Configure the app before it is imported: a throwaway SQLite file, photos on disk, events in memory.
_TMP = Path(tempfile.mkdtemp(prefix="drivenow-tests-"))
os.environ.update(
    DATABASE_URL=f"sqlite+aiosqlite:///{(_TMP / 'test.db').as_posix()}",
    STORAGE_BACKEND="local",
    LOCAL_STORAGE_DIR=str(_TMP / "storage"),
    MESSAGING_BACKEND="memory",
    SECRETS_BACKEND="env",
    JWT_SECRET="unit-test-secret-that-is-long-enough-for-hs256",
    DRIVENOW_BUGS="off",
    LLM_PROVIDER="mock",
)

import httpx  # noqa: E402
import pytest  # noqa: E402
from PIL import Image  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.db import Base, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.messaging import MemoryEventBus  # noqa: E402
from app.seed import seed  # noqa: E402

PASSWORD = "DriveNow!2026"


@pytest.fixture(scope="session", autouse=True)
async def database() -> AsyncIterator[None]:
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with app.router.lifespan_context(app):
        await seed(app.state.storage)
        yield
    await engine.dispose()


@pytest.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
        yield http


@pytest.fixture
def bugs_on() -> object:
    settings = get_settings()
    settings.drivenow_bugs = "on"
    yield
    settings.drivenow_bugs = "off"


@pytest.fixture
def bus() -> MemoryEventBus:
    return app.state.bus  # type: ignore[no-any-return]


async def login(client: httpx.AsyncClient, email: str) -> dict[str, str]:
    response = await client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


_plate = 0


def car_payload(**changes: object) -> dict[str, object]:
    global _plate
    _plate += 1
    return {
        "make": "Unit",
        "model": "Test",
        "year": 2022,
        "category": "suv",
        "transmission": "automatic",
        "fuel_type": "diesel",
        "seats": 5,
        "doors": 5,
        "mileage_km": 1000,
        "color": "Red",
        "license_plate": f"UT {_plate:04d}",
        "daily_price": 50.0,
        "deposit": 100,
        "city": "Prishtina",
        **changes,
    }


def png_bytes() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (20, 10), "blue").save(buffer, "PNG")
    return buffer.getvalue()
