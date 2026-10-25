from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CarStatus, User
from app.presenters import booking_out
from app.schemas import StatsOut
from app.services import bookings, cars, users


async def collect_stats(db: AsyncSession, admin: User) -> StatsOut:
    return StatsOut(
        cars=await cars.count_cars(db),
        available_cars=await cars.count_cars(db, CarStatus.AVAILABLE),
        active_bookings=await bookings.count_active(db),
        revenue_this_month=await bookings.revenue_this_month(db),
        users=await users.count_users(db),
        recent_bookings=[booking_out(b) for b in await bookings.list_bookings(db, admin, limit=5)],
    )
