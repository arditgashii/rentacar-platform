"""Turns booking events into notifications for the client and the car owner."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.messaging import Event, Handler
from app.models import Notification, User


def event_handler(sessions: async_sessionmaker[AsyncSession]) -> Handler:
    async def handle(event: Event) -> None:
        async with sessions() as db:
            for user_id in {event["client_id"], event["owner_id"]}:
                db.add(Notification(user_id=user_id, type=event["type"], payload=event))
            await db.commit()

    return handle


async def list_notifications(db: AsyncSession, user: User) -> list[Notification]:
    query = (
        select(Notification)
        .where(Notification.user_id == user.id)
        .order_by(Notification.created_at.desc(), Notification.id.desc())
        .limit(100)
    )
    return list(await db.scalars(query))
