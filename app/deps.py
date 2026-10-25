from typing import Annotated

from fastapi import Depends, Request

from app.messaging import EventBus
from app.storage import PhotoStorage


def _storage(request: Request) -> PhotoStorage:
    return request.app.state.storage


def _bus(request: Request) -> EventBus:
    return request.app.state.bus


Storage = Annotated[PhotoStorage, Depends(_storage)]
Bus = Annotated[EventBus, Depends(_bus)]
