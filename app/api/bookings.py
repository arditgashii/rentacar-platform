from fastapi import APIRouter

from app.deps import Bus
from app.presenters import booking_out
from app.schemas import BookingIn, BookingOut, NotificationOut
from app.security import AdminUser, CurrentUser, Db
from app.services import bookings, notifications

router = APIRouter(tags=["bookings"])


@router.post("/bookings", response_model=BookingOut, status_code=201)
async def create_booking(data: BookingIn, db: Db, bus: Bus, user: CurrentUser) -> BookingOut:
    return booking_out(await bookings.create_booking(db, bus, user, data))


@router.get("/bookings", response_model=list[BookingOut])
async def list_bookings(db: Db, user: CurrentUser) -> list[BookingOut]:
    return [booking_out(b) for b in await bookings.list_bookings(db, user)]


@router.get("/bookings/{booking_id}", response_model=BookingOut)
async def get_booking(booking_id: int, db: Db, user: CurrentUser) -> BookingOut:
    return booking_out(await bookings.get_booking(db, user, booking_id))


@router.post("/bookings/{booking_id}/cancel", response_model=BookingOut)
async def cancel_booking(booking_id: int, db: Db, bus: Bus, user: CurrentUser) -> BookingOut:
    return booking_out(await bookings.cancel_booking(db, bus, user, booking_id))


@router.post("/bookings/{booking_id}/confirm", response_model=BookingOut)
async def confirm_booking(booking_id: int, db: Db, bus: Bus, _: AdminUser) -> BookingOut:
    return booking_out(await bookings.confirm_booking(db, bus, booking_id))


@router.get("/notifications", response_model=list[NotificationOut], tags=["notifications"])
async def my_notifications(db: Db, user: CurrentUser) -> list[NotificationOut]:
    return [NotificationOut.model_validate(n) for n in await notifications.list_notifications(db, user)]
