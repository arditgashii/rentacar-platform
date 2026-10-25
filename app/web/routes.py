from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from pydantic import ValidationError
from starlette.datastructures import FormData, UploadFile

from app.config import get_settings
from app.db import SessionLocal
from app.errors import AppError
from app.llm import generate_description
from app.models import CarStatus, Category, Feature, FuelType, Role, Transmission
from app.presenters import booking_out, car_out
from app.schemas import AdminUserPatch, BookingIn, CarCreate, CarUpdate, LoginIn, RegisterIn, UserOut
from app.security import COOKIE_NAME, create_token
from app.services import bookings, cars, photos, users
from app.services.stats import collect_stats
from app.web.support import (
    current_user,
    form_errors,
    read_form,
    redirect,
    render,
    require_user,
)

router = APIRouter(include_in_schema=False)

CITIES = ["Prishtina", "Prizren", "Peja", "Gjakova", "Ferizaj", "Tirana"]
CHOICES: dict[str, Any] = {
    "categories": list(Category),
    "transmissions": list(Transmission),
    "fuel_types": list(FuelType),
    "statuses": list(CarStatus),
    "features": list(Feature),
    "cities": CITIES,
}
CAR_FIELDS = list(CarCreate.model_fields)


def _safe_next(value: str | None) -> str:
    """Only local paths, so a login link cannot send people to another site."""
    return value if value and value.startswith("/") and not value.startswith("//") else "/cars"


def _decimal(value: str | None) -> Decimal | None:
    try:
        return Decimal(value) if value else None
    except InvalidOperation:
        return None


def _int(value: str | None) -> int | None:
    return int(value) if value and value.isdigit() else None


# Home, login, register


@router.get("/", response_class=HTMLResponse)
async def home(request: Request) -> HTMLResponse:
    async with SessionLocal() as db:
        featured, total = await cars.list_cars(db, None, cars.CarFilters(page_size=6))
    return await render(request, "home.html", cars=[car_out(c) for c in featured], total=total, **CHOICES)


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request) -> Response:
    if await current_user(request):
        return redirect(request, "/cars")
    return await render(request, "login.html", next=_safe_next(request.query_params.get("next")))


@router.post("/login")
async def login(request: Request) -> Response:
    form = await read_form(request)
    next_path = _safe_next(str(form.get("next", "")))
    email = str(form.get("email", "")).strip()
    try:
        data = LoginIn(email=email, password=str(form.get("password", "")))
        async with SessionLocal() as db:
            user = await users.authenticate(db, data.email, data.password)
    except (ValidationError, AppError) as error:
        message = error.detail if isinstance(error, AppError) else "Enter a valid email and password."
        return await render(
            request, "login.html", status_code=400, error=message, email=email, next=next_path
        )
    response = redirect(
        request, "/admin" if user.role == Role.ADMIN else next_path, f"Welcome back, {user.full_name}."
    )
    response.set_cookie(
        COOKIE_NAME,
        create_token(user),
        httponly=True,
        samesite="lax",
        max_age=get_settings().jwt_expire_minutes * 60,
    )
    return response


@router.post("/logout")
async def logout(request: Request) -> Response:
    await read_form(request)
    response = redirect(request, "/", "You are logged out.")
    response.delete_cookie(COOKIE_NAME)
    return response


@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request) -> HTMLResponse:
    return await render(request, "register.html", values={}, errors={}, cities=CITIES)


@router.post("/register")
async def register(request: Request) -> Response:
    form = await read_form(request)
    values = {k: str(form.get(k, "")).strip() for k in ("email", "full_name", "phone", "city")}
    try:
        data = RegisterIn(**values, password=str(form.get("password", "")))
        async with SessionLocal() as db:
            user = await users.register(db, data)
    except ValidationError as error:
        return await render(
            request, "register.html", 400, values=values, errors=form_errors(error), cities=CITIES
        )
    except AppError as error:
        return await render(
            request, "register.html", 400, values=values, errors={"email": error.detail}, cities=CITIES
        )
    response = redirect(request, "/cars", "Your account is ready.")
    response.set_cookie(COOKIE_NAME, create_token(user), httponly=True, samesite="lax")
    return response


# Browsing


@router.get("/cars", response_class=HTMLResponse)
async def car_list(request: Request) -> HTMLResponse:
    params = request.query_params
    filters = cars.CarFilters(
        q=params.get("q") or None,
        city=params.get("city") or None,
        category=params.get("category") or None,
        transmission=params.get("transmission") or None,
        fuel_type=params.get("fuel_type") or None,
        min_price=_decimal(params.get("min_price")),
        max_price=_decimal(params.get("max_price")),
        seats=_int(params.get("seats")),
        sort=params.get("sort") or "newest",
        page=max(_int(params.get("page")) or 1, 1),
        page_size=12,
    )
    async with SessionLocal() as db:
        # The public list always shows available cars only, also for admins.
        items, total = await cars.list_cars(db, None, filters)
    pages = max((total + filters.page_size - 1) // filters.page_size, 1)
    return await render(
        request,
        "cars/list.html",
        cars=[car_out(c) for c in items],
        total=total,
        page=filters.page,
        pages=pages,
        params=params,
        **CHOICES,
    )


@router.get("/cars/new", response_class=HTMLResponse)
async def new_car_page(request: Request) -> HTMLResponse:
    await require_user(request)
    defaults = {"status": CarStatus.AVAILABLE, "deposit": "0", "seats": "5", "doors": "5"}
    return await render(request, "cars/form.html", car=None, values=defaults, errors={}, **CHOICES)


def _car_values(form: FormData) -> dict[str, Any]:
    """Form fields as a dict; empty optional fields are left out so their defaults apply."""
    values: dict[str, Any] = {
        f: str(form.get(f, "")).strip() for f in CAR_FIELDS if f != "features" and form.get(f)
    }
    values["features"] = form.getlist("features")
    return values


def _uploads(form: FormData) -> list[UploadFile]:
    return [f for f in form.getlist("photos") if isinstance(f, UploadFile) and f.filename]


@router.post("/cars/new")
async def create_car(request: Request) -> Response:
    user = await require_user(request)
    form = await read_form(request)
    values = _car_values(form)
    try:
        data = CarCreate.model_validate(values)
    except ValidationError as error:
        return await render(
            request, "cars/form.html", 400, car=None, values=values, errors=form_errors(error), **CHOICES
        )
    async with SessionLocal() as db:
        try:
            car = await cars.create_car(db, user, data)
        except AppError as error:
            return await render(
                request,
                "cars/form.html",
                400,
                car=None,
                values=values,
                errors={"license_plate": error.detail},
                **CHOICES,
            )
        problems = await _save_photos(request, db, user, car.id, _uploads(form))
    message = "Car published." if not problems else f"Car published. {problems[0]}"
    return redirect(request, f"/cars/{car.id}/edit", message, "success" if not problems else "error")


async def _save_photos(
    request: Request, db: Any, user: Any, car_id: int, files: list[UploadFile]
) -> list[str]:
    problems = []
    for upload in files:
        data = await upload.read(photos.MAX_BYTES + 1)
        try:
            await photos.add_photo(db, request.app.state.storage, user, car_id, data)
        except AppError as error:
            problems.append(f"{upload.filename}: {error.detail}")
    return problems


@router.get("/cars/{car_id}", response_class=HTMLResponse)
async def car_detail(request: Request, car_id: int) -> HTMLResponse:
    user = await current_user(request)
    async with SessionLocal() as db:
        car = await cars.get_car(db, user, car_id)
    tomorrow = date.today() + timedelta(days=1)
    return await render(
        request,
        "cars/detail.html",
        car=car_out(car),
        can_manage=cars.can_manage(user, car),
        can_book=user is not None and user.role == Role.CLIENT and car.owner_id != user.id,
        default_start=tomorrow,
        default_end=tomorrow + timedelta(days=3),
        today=date.today(),
    )


@router.post("/cars/{car_id}/book")
async def book_car(request: Request, car_id: int) -> Response:
    user = await require_user(request, Role.CLIENT)
    form = await read_form(request)
    try:
        data = BookingIn(
            car_id=car_id,
            start_date=date.fromisoformat(str(form.get("start_date"))),
            end_date=date.fromisoformat(str(form.get("end_date"))),
        )
        async with SessionLocal() as db:
            await bookings.create_booking(db, request.app.state.bus, user, data)
    except (ValueError, ValidationError):
        return redirect(request, f"/cars/{car_id}", "Choose a pickup and a return date.", "error")
    except AppError as error:
        return redirect(request, f"/cars/{car_id}", error.detail, "error")
    return redirect(request, "/my/bookings", "Booking requested. The owner will confirm it soon.")


# Managing a car


@router.get("/cars/{car_id}/edit", response_class=HTMLResponse)
async def edit_car_page(request: Request, car_id: int) -> HTMLResponse:
    user = await require_user(request)
    async with SessionLocal() as db:
        car = await cars.get_car(db, user, car_id)
    if not cars.can_manage(user, car):
        raise AppError(403, "FORBIDDEN", "Only the owner or an admin can edit this car.")
    out = car_out(car)
    return await render(request, "cars/form.html", car=out, values=out.model_dump(), errors={}, **CHOICES)


@router.post("/cars/{car_id}/edit")
async def edit_car(request: Request, car_id: int) -> Response:
    user = await require_user(request)
    form = await read_form(request)
    values = _car_values(form)
    async with SessionLocal() as db:
        try:
            data = CarUpdate.model_validate(values)
            await cars.update_car(db, user, car_id, data)
        except ValidationError as error:
            car = car_out(await cars.get_car(db, user, car_id))
            return await render(
                request, "cars/form.html", 400, car=car, values=values, errors=form_errors(error), **CHOICES
            )
        except AppError as error:
            if error.status in (403, 404):
                raise
            car = car_out(await cars.get_car(db, user, car_id))
            return await render(
                request,
                "cars/form.html",
                400,
                car=car,
                values=values,
                errors={"license_plate": error.detail},
                **CHOICES,
            )
    return redirect(request, f"/cars/{car_id}/edit", "Changes saved.")


@router.post("/cars/{car_id}/delete")
async def delete_car(request: Request, car_id: int) -> Response:
    user = await require_user(request)
    await read_form(request)
    async with SessionLocal() as db:
        await cars.delete_car(db, request.app.state.storage, user, car_id)
    back = "/admin/cars" if user.role == Role.ADMIN else "/my/listings"
    return redirect(request, back, "Car deleted.")


@router.post("/cars/{car_id}/photos")
async def upload_photos(request: Request, car_id: int) -> Response:
    user = await require_user(request)
    form = await read_form(request)
    files = _uploads(form)
    if not files:
        return redirect(request, f"/cars/{car_id}/edit", "Choose at least one photo.", "error")
    async with SessionLocal() as db:
        problems = await _save_photos(request, db, user, car_id, files)
    if problems:
        return redirect(request, f"/cars/{car_id}/edit", " ".join(problems), "error")
    return redirect(request, f"/cars/{car_id}/edit", "Photos uploaded.")


@router.post("/cars/{car_id}/photos/{photo_id}/{action}")
async def photo_action(request: Request, car_id: int, photo_id: int, action: str) -> Response:
    user = await require_user(request)
    await read_form(request)
    async with SessionLocal() as db:
        if action == "delete":
            await photos.delete_photo(db, request.app.state.storage, user, car_id, photo_id)
            message = "Photo deleted."
        elif action == "primary":
            await photos.set_primary(db, user, car_id, photo_id)
            message = "Main photo changed."
        elif action in ("up", "down"):
            await photos.move_photo(db, user, car_id, photo_id, -1 if action == "up" else 1)
            message = "Photo moved."
        else:
            raise AppError(404, "NOT_FOUND", "Unknown action.")
    return redirect(request, f"/cars/{car_id}/edit", message)


@router.post("/cars/{car_id}/describe")
async def describe_car(request: Request, car_id: int) -> JSONResponse:
    user = await require_user(request)
    await read_form(request)
    async with SessionLocal() as db:
        car = await cars.get_car(db, user, car_id)
        if not cars.can_manage(user, car):
            raise AppError(403, "FORBIDDEN", "Only the owner or an admin can do this.")
        text, provider = await generate_description(car)
    return JSONResponse({"description": text, "provider": provider})


# My pages


@router.get("/my/listings", response_class=HTMLResponse)
async def my_listings(request: Request) -> HTMLResponse:
    user = await require_user(request)
    async with SessionLocal() as db:
        items, _ = await cars.list_cars(db, user, cars.CarFilters(owner_id=user.id, page_size=50))
    return await render(request, "my/listings.html", cars=[car_out(c) for c in items])


@router.get("/my/bookings", response_class=HTMLResponse)
async def my_bookings(request: Request) -> HTMLResponse:
    user = await require_user(request)
    async with SessionLocal() as db:
        items = await bookings.list_bookings(db, user) if user.role == Role.CLIENT else []
    return await render(request, "my/bookings.html", bookings=[booking_out(b) for b in items])


@router.post("/bookings/{booking_id}/{action}")
async def booking_action(request: Request, booking_id: int, action: str) -> Response:
    user = await require_user(request)
    form = await read_form(request)
    back = _safe_next(str(form.get("back", "/my/bookings")))
    async with SessionLocal() as db:
        try:
            if action == "cancel":
                await bookings.cancel_booking(db, request.app.state.bus, user, booking_id)
                message = "Booking cancelled."
            elif action == "confirm" and user.role == Role.ADMIN:
                await bookings.confirm_booking(db, request.app.state.bus, booking_id)
                message = "Booking confirmed."
            else:
                raise AppError(404, "NOT_FOUND", "Unknown action.")
        except AppError as error:
            if error.status == 404:
                raise
            return redirect(request, back, error.detail, "error")
    return redirect(request, back, message)


# Admin


@router.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(request: Request) -> HTMLResponse:
    admin = await require_user(request, Role.ADMIN)
    async with SessionLocal() as db:
        stats = await collect_stats(db, admin)
    return await render(request, "admin/dashboard.html", stats=stats)


@router.get("/admin/cars", response_class=HTMLResponse)
async def admin_cars(request: Request) -> HTMLResponse:
    admin = await require_user(request, Role.ADMIN)
    status = request.query_params.get("status") or None
    async with SessionLocal() as db:
        items, total = await cars.list_cars(
            db, admin, cars.CarFilters(status=status, q=request.query_params.get("q"), page_size=50)
        )
    return await render(
        request, "admin/cars.html", cars=[car_out(c) for c in items], total=total, status=status, **CHOICES
    )


@router.get("/admin/users", response_class=HTMLResponse)
async def admin_users(request: Request) -> HTMLResponse:
    await require_user(request, Role.ADMIN)
    async with SessionLocal() as db:
        items = await users.list_users(db)
    return await render(request, "admin/users.html", users=[UserOut.model_validate(u) for u in items])


@router.post("/admin/users/{user_id}")
async def admin_update_user(request: Request, user_id: int) -> Response:
    admin = await require_user(request, Role.ADMIN)
    form = await read_form(request)
    change = str(form.get("change", ""))
    patch = {
        "activate": AdminUserPatch(is_active=True),
        "deactivate": AdminUserPatch(is_active=False),
        "make_admin": AdminUserPatch(role=Role.ADMIN),
        "make_client": AdminUserPatch(role=Role.CLIENT),
    }.get(change)
    if patch is None:
        raise AppError(400, "BAD_REQUEST", "Unknown change.")
    async with SessionLocal() as db:
        try:
            await users.update_user(db, admin, user_id, patch)
        except AppError as error:
            if error.status == 404:
                raise
            return redirect(request, "/admin/users", error.detail, "error")
    return redirect(request, "/admin/users", "User updated.")


@router.get("/admin/bookings", response_class=HTMLResponse)
async def admin_bookings(request: Request) -> HTMLResponse:
    admin = await require_user(request, Role.ADMIN)
    async with SessionLocal() as db:
        items = await bookings.list_bookings(db, admin)
    return await render(request, "admin/bookings.html", bookings=[booking_out(b) for b in items])
