import logging
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import ColumnElement, and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.errors import AppError, forbidden, not_found
from app.messaging import Event, EventBus
from app.models import Booking, BookingStatus, Car, CarStatus, Role, User
from app.schemas import BookingIn

MAX_DAYS = 30
ACTIVE = (BookingStatus.PENDING, BookingStatus.CONFIRMED)
log = logging.getLogger(__name__)


async def _publish(bus: EventBus, event: Event) -> None:
    """The booking is already saved, so a bus outage must not turn the request into an error.
    The lost event is logged with everything needed to replay it."""
    try:
        await bus.publish(event)
    except Exception:
        log.exception("could not publish %s for booking %s: %s", event["type"], event["booking_id"], event)


def booking_event(event_type: str, booking: Booking) -> Event:
    return {
        "type": event_type,
        "booking_id": booking.id,
        "car_id": booking.car_id,
        "client_id": booking.client_id,
        "owner_id": booking.car.owner_id,
        "start_date": booking.start_date.isoformat(),
        "end_date": booking.end_date.isoformat(),
        "total_price": str(booking.total_price),
        "occurred_at": datetime.now(UTC).isoformat(),
    }


def _overlap_condition(start: date, end: date) -> ColumnElement[bool]:
    """Bookings are [start_date, end_date): the car is free again on the end date."""
    if get_settings().bugs_on:
        # BUG-002: only checks whether the new start falls inside an existing booking, so a booking
        # that starts before and ends after an existing one is accepted.
        return and_(Booking.start_date <= start, start < Booking.end_date)
    return and_(Booking.start_date < end, start < Booking.end_date)


async def create_booking(db: AsyncSession, bus: EventBus, user: User, data: BookingIn) -> Booking:
    if user.role != Role.CLIENT:
        raise forbidden("Only clients can book cars.")
    if data.end_date <= data.start_date:
        raise AppError(400, "INVALID_DATES", "The return date must be after the pickup date.")
    if data.start_date < date.today():
        raise AppError(400, "START_IN_PAST", "The pickup date cannot be in the past.")
    days = (data.end_date - data.start_date).days
    if days > MAX_DAYS:
        raise AppError(400, "TOO_LONG", f"A booking can be at most {MAX_DAYS} days.")

    # Lock the car row so two bookings for the same car are checked one after the other.
    car = await db.scalar(select(Car).where(Car.id == data.car_id).with_for_update())
    if car is None:
        raise not_found("car")
    if car.owner_id == user.id:
        raise AppError(400, "OWN_CAR", "You cannot book your own car.")
    if car.status != CarStatus.AVAILABLE:
        raise AppError(409, "CAR_NOT_AVAILABLE", "This car cannot be booked right now.")

    clash = await db.scalar(
        select(Booking.id).where(
            Booking.car_id == car.id,
            Booking.status.in_(ACTIVE),
            _overlap_condition(data.start_date, data.end_date),
        )
    )
    if clash:
        raise AppError(409, "DATES_TAKEN", "The car is already booked for some of these dates.")

    booking = Booking(
        car_id=car.id,
        client_id=user.id,
        start_date=data.start_date,
        end_date=data.end_date,
        days=days,
        total_price=(car.daily_price * days).quantize(Decimal("0.01")),
        status=BookingStatus.PENDING,
    )
    db.add(booking)
    await db.commit()
    await db.refresh(booking)
    await _publish(bus, booking_event("booking.created", booking))
    return booking


async def list_bookings(db: AsyncSession, user: User, limit: int | None = None) -> list[Booking]:
    query = select(Booking).order_by(Booking.created_at.desc(), Booking.id.desc())
    if user.role != Role.ADMIN:
        query = query.where(Booking.client_id == user.id)
    if limit:
        query = query.limit(limit)
    return list((await db.scalars(query)).unique())


async def get_booking(db: AsyncSession, user: User, booking_id: int) -> Booking:
    booking = await db.get(Booking, booking_id)
    if booking is None or (user.role != Role.ADMIN and booking.client_id != user.id):
        raise not_found("booking")
    return booking


async def cancel_booking(db: AsyncSession, bus: EventBus, user: User, booking_id: int) -> Booking:
    booking = await get_booking(db, user, booking_id)
    if booking.status not in ACTIVE:
        raise AppError(409, "NOT_CANCELLABLE", f"A {booking.status} booking cannot be cancelled.")
    booking.status = BookingStatus.CANCELLED
    await db.commit()
    await _publish(bus, booking_event("booking.cancelled", booking))
    return booking


async def confirm_booking(db: AsyncSession, bus: EventBus, booking_id: int) -> Booking:
    booking = await db.get(Booking, booking_id)
    if booking is None:
        raise not_found("booking")
    if booking.status != BookingStatus.PENDING:
        raise AppError(409, "NOT_PENDING", "Only pending bookings can be confirmed.")
    booking.status = BookingStatus.CONFIRMED
    await db.commit()
    await _publish(bus, booking_event("booking.confirmed", booking))
    return booking


async def count_active(db: AsyncSession) -> int:
    return int(await db.scalar(select(func.count(Booking.id)).where(Booking.status.in_(ACTIVE))) or 0)


async def revenue_this_month(db: AsyncSession) -> Decimal:
    first_day = date.today().replace(day=1)
    total = await db.scalar(
        select(func.coalesce(func.sum(Booking.total_price), 0)).where(
            Booking.status.in_((BookingStatus.CONFIRMED, BookingStatus.COMPLETED)),
            Booking.start_date >= first_day,
        )
    )
    return Decimal(str(total or 0)).quantize(Decimal("0.01"))
