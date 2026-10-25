import re
import subprocess
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app.api import api_router
from app.config import get_settings
from app.db import SessionLocal
from app.errors import AppError, register_error_handlers
from app.messaging import build_event_bus
from app.observability import setup_logging, setup_observability
from app.services.notifications import event_handler
from app.storage import build_storage
from app.web import web_router
from app.web.support import LoginRequired, error_page, login_redirect

STATIC_DIR = Path(__file__).parent / "web" / "static"
BLOB_NAME = re.compile(r"^cars/\d+/[0-9a-f]{32}\.(jpg|png|webp)$")


@lru_cache
def current_commit() -> str:
    """The commit baked into the image, or the local git commit when running from a checkout."""
    if get_settings().commit:
        return get_settings().commit
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, timeout=5, check=True
        )
        return result.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return "unknown"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.storage = build_storage()
    app.state.bus = build_event_bus()
    await app.state.storage.start()
    await app.state.bus.start(event_handler(SessionLocal))
    yield
    await app.state.bus.close()
    await app.state.storage.close()


def create_app() -> FastAPI:
    setup_logging()
    settings = get_settings()
    app = FastAPI(
        title="DriveNow API",
        version=settings.version,
        description="Rent-a-car marketplace. Clients list their cars and book other people's cars.",
        lifespan=lifespan,
    )
    register_error_handlers(app, error_page)
    app.add_exception_handler(LoginRequired, login_redirect)  # type: ignore[arg-type]
    setup_observability(app)
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    app.include_router(api_router)
    app.include_router(web_router)

    @app.get("/health", tags=["health"])
    async def health() -> dict[str, str]:
        return {"status": "ok", "version": settings.version, "commit": current_commit()}

    @app.get("/health/ready", tags=["health"])
    async def ready(request: Request) -> JSONResponse:
        checks: dict[str, str] = {}
        try:
            async with SessionLocal() as db:
                await db.execute(text("SELECT 1"))
            checks["database"] = "ok"
        except Exception as error:
            checks["database"] = f"error: {type(error).__name__}"
        for name, component in (("storage", request.app.state.storage), ("bus", request.app.state.bus)):
            try:
                await component.ping()
                checks[name] = "ok"
            except Exception as error:
                checks[name] = f"error: {type(error).__name__}"
        healthy = all(value == "ok" for value in checks.values())
        return JSONResponse(
            status_code=200 if healthy else 503,
            content={"status": "ok" if healthy else "unavailable", "checks": checks},
        )

    @app.get("/media/{blob_name:path}", include_in_schema=False)
    async def media(blob_name: str, request: Request) -> Response:
        if not BLOB_NAME.match(blob_name):
            raise AppError(404, "PHOTO_NOT_FOUND", "Photo not found.")
        found = await request.app.state.storage.download(blob_name)
        if found is None:
            raise AppError(404, "PHOTO_NOT_FOUND", "Photo not found.")
        data, content_type = found
        return Response(data, media_type=content_type, headers={"Cache-Control": "public, max-age=86400"})

    return app


app = create_app()
