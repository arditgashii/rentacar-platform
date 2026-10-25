"""Booking events go to an Azure Service Bus topic (the emulator locally).

The topic has two subscriptions: `notifications`, read by the worker, and `audit`, which nobody
consumes and which tests peek to prove an event was published. `memory` keeps events in the app
process and hands them to the same handler, for unit tests and runs without Docker.
"""

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any, Protocol

from azure.servicebus import ServiceBusMessage
from azure.servicebus.aio import ServiceBusClient

from app.config import get_settings

log = logging.getLogger(__name__)

Event = dict[str, Any]
Handler = Callable[[Event], Awaitable[None]]


class EventBus(Protocol):
    async def start(self, handler: Handler) -> None: ...
    async def close(self) -> None: ...
    async def publish(self, event: Event) -> None: ...
    async def ping(self) -> None: ...


class ServiceBusEventBus:
    def __init__(self, connection_string: str, topic: str) -> None:
        self._client = ServiceBusClient.from_connection_string(connection_string)
        self._topic = topic
        self._sender = self._client.get_topic_sender(topic)

    async def start(self, handler: Handler) -> None:
        # The worker process consumes the topic; the API only publishes.
        pass

    async def close(self) -> None:
        await self._sender.close()
        await self._client.close()

    async def publish(self, event: Event) -> None:
        message = ServiceBusMessage(
            json.dumps(event, default=str),
            content_type="application/json",
            subject=event["type"],
            application_properties={"booking_id": event.get("booking_id", 0)},
        )
        await self._sender.send_messages(message)

    async def ping(self) -> None:
        receiver = self._client.get_subscription_receiver(self._topic, "audit")
        async with receiver:
            await receiver.peek_messages(max_message_count=1)


class MemoryEventBus:
    def __init__(self) -> None:
        self._queue: asyncio.Queue[Event] = asyncio.Queue()
        self._task: asyncio.Task[None] | None = None
        self.published: list[Event] = []

    async def start(self, handler: Handler) -> None:
        async def consume() -> None:
            while True:
                event = await self._queue.get()
                try:
                    await handler(event)
                except Exception:
                    log.exception("event handler failed", extra={"event": event})
                finally:
                    self._queue.task_done()

        self._task = asyncio.create_task(consume())

    async def close(self) -> None:
        if self._task:
            self._task.cancel()

    async def publish(self, event: Event) -> None:
        self.published.append(event)
        await self._queue.put(event)

    async def drain(self) -> None:
        """Wait until every published event was handled (used by unit tests)."""
        await self._queue.join()

    async def ping(self) -> None:
        pass


def build_event_bus() -> EventBus:
    settings = get_settings()
    if settings.messaging_backend == "servicebus":
        return ServiceBusEventBus(settings.servicebus_connection_string, settings.booking_topic)
    return MemoryEventBus()
