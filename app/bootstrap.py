"""Container start-up: wait for the database, create it on SQL Server, migrate, seed.

Run with `python -m app.bootstrap` before starting the API.
"""

import asyncio
import logging
import time

from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import get_settings
from app.observability import setup_logging
from app.seed import main as seed_main

log = logging.getLogger("drivenow.bootstrap")


async def _create_database_if_missing(timeout_seconds: int = 120) -> None:
    url = make_url(get_settings().database_url)
    if not url.drivername.startswith("mssql"):
        return
    master = create_async_engine(url.set(database="master"), isolation_level="AUTOCOMMIT")
    deadline = time.monotonic() + timeout_seconds
    try:
        while True:
            try:
                async with master.connect() as connection:
                    await connection.execute(
                        text(f"IF DB_ID(N'{url.database}') IS NULL CREATE DATABASE [{url.database}]")
                    )
                return
            except Exception as error:
                if time.monotonic() > deadline:
                    raise
                log.info("waiting for SQL Server: %s", type(error).__name__)
                await asyncio.sleep(3)
    finally:
        await master.dispose()


def main() -> None:
    setup_logging()
    asyncio.run(_create_database_if_missing())
    command.upgrade(Config("alembic.ini"), "head")
    log.info("database migrated")
    if get_settings().seed_on_start:
        asyncio.run(seed_main())


if __name__ == "__main__":
    main()
