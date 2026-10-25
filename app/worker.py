"""Consumes booking events from the Service Bus subscription `notifications`.

A message that cannot be handled is dead-lettered after the delivery limit, so one bad message never
blocks the queue. Run with `python -m app.worker`.
"""

import asyncio
import json
import logging

from azure.servicebus import ServiceBusReceivedMessage
from azure.servicebus.aio import ServiceBusClient, ServiceBusReceiver
from azure.servicebus.exceptions import ServiceBusError

from app.config import get_settings
from app.db import SessionLocal
from app.messaging import Handler
from app.observability import setup_logging
from app.services.notifications import event_handler

log = logging.getLogger("drivenow.worker")
SUBSCRIPTION = "notifications"


async def _handle(receiver: ServiceBusReceiver, message: ServiceBusReceivedMessage, handler: Handler) -> None:
    try:
        event = json.loads(str(message))
        await handler(event)
    except (ValueError, KeyError) as error:
        log.error("bad message, dead-lettering: %s", error)
        await receiver.dead_letter_message(message, reason="invalid", error_description=str(error))
        return
    except Exception:
        log.exception("handling failed, the message will be retried")
        await receiver.abandon_message(message)
        return
    await receiver.complete_message(message)
    log.info("handled %s for booking %s", event["type"], event.get("booking_id"))


async def run() -> None:
    settings = get_settings()
    handler = event_handler(SessionLocal)
    while True:
        try:
            async with ServiceBusClient.from_connection_string(
                settings.servicebus_connection_string
            ) as client:
                receiver = client.get_subscription_receiver(settings.booking_topic, SUBSCRIPTION)
                async with receiver:
                    log.info("worker listening on %s/%s", settings.booking_topic, SUBSCRIPTION)
                    while True:
                        for message in await receiver.receive_messages(max_message_count=20, max_wait_time=5):
                            await _handle(receiver, message, handler)
        except ServiceBusError:
            log.exception("lost the connection to Service Bus, reconnecting in 5 seconds")
            await asyncio.sleep(5)


if __name__ == "__main__":
    setup_logging()
    asyncio.run(run())
