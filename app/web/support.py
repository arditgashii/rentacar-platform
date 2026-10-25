"""Plumbing for the server-rendered pages: current user, CSRF, flash messages, templates."""

import json
import secrets
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from fastapi import Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError
from starlette.datastructures import FormData

from app.db import SessionLocal
from app.errors import AppError
from app.labels import label
from app.models import Role, User
from app.security import COOKIE_NAME, user_from_token

templates = Jinja2Templates(directory=Path(__file__).parent / "templates")
CSRF_COOKIE = "csrf_token"
FLASH_COOKIE = "flash"


def _money(value: Any) -> str:
    return f"{float(value):,.2f}"


templates.env.filters["money"] = _money
templates.env.filters["label"] = label


async def current_user(request: Request) -> User | None:
    if not hasattr(request.state, "user"):
        async with SessionLocal() as db:
            request.state.user = await user_from_token(db, request.cookies.get(COOKIE_NAME))
    return request.state.user


class LoginRequired(Exception):
    """Raised by a page that needs a logged-in user; turns into a redirect to /login."""

    def __init__(self, next_path: str) -> None:
        self.next_path = next_path


async def require_user(request: Request, role: Role | None = None) -> User:
    user = await current_user(request)
    if user is None:
        raise LoginRequired(request.url.path)
    if role is not None and user.role != role:
        raise AppError(403, "FORBIDDEN", "You are not allowed to open this page.")
    return user


def _csrf_token(request: Request) -> str:
    if not hasattr(request.state, "csrf"):
        request.state.csrf = request.cookies.get(CSRF_COOKIE) or secrets.token_urlsafe(24)
    return request.state.csrf


async def read_form(request: Request) -> FormData:
    """Reads a posted form and checks its CSRF token against the cookie."""
    form = await request.form()
    cookie = request.cookies.get(CSRF_COOKIE)
    sent = form.get("csrf_token") or request.headers.get("X-CSRF-Token")
    if not cookie or not isinstance(sent, str) or not secrets.compare_digest(cookie, sent):
        raise AppError(400, "CSRF_FAILED", "The form expired. Reload the page and try again.")
    return form


def _with_cookies(request: Request, response: HTMLResponse | RedirectResponse) -> None:
    if request.cookies.get(CSRF_COOKIE) != _csrf_token(request):
        response.set_cookie(CSRF_COOKIE, _csrf_token(request), httponly=True, samesite="lax")


async def render(request: Request, template: str, status_code: int = 200, **context: Any) -> HTMLResponse:
    flash = None
    if raw := request.cookies.get(FLASH_COOKIE):
        try:
            flash = json.loads(raw)
        except ValueError:
            flash = None
    response = templates.TemplateResponse(
        request,
        template,
        {
            "user": await current_user(request),
            "csrf_token": _csrf_token(request),
            "flash": flash,
            **context,
        },
        status_code=status_code,
    )
    if flash is not None or raw:
        response.delete_cookie(FLASH_COOKIE)
    _with_cookies(request, response)
    return response


def redirect(request: Request, url: str, message: str = "", kind: str = "success") -> RedirectResponse:
    response = RedirectResponse(url, status_code=303)
    if message:
        response.set_cookie(
            FLASH_COOKIE, json.dumps({"kind": kind, "message": message}), max_age=30, samesite="lax"
        )
    _with_cookies(request, response)
    return response


def form_errors(error: ValidationError) -> dict[str, str]:
    """Field name -> first readable message."""
    errors: dict[str, str] = {}
    for problem in error.errors():
        field = str(problem["loc"][0]) if problem["loc"] else "form"
        message = str(problem["msg"]).removeprefix("Value error, ")
        errors.setdefault(field, message[0].upper() + message[1:])
    return errors


async def error_page(request: Request, status: int, message: str) -> HTMLResponse:
    return await render(request, "error.html", status_code=status, status=status, message=message)


async def login_redirect(request: Request, exc: LoginRequired) -> RedirectResponse:
    return redirect(request, f"/login?{urlencode({'next': exc.next_path})}", "Log in to continue.", "error")


def page_url(request: Request, **changes: Any) -> str:
    params = {k: v for k, v in request.query_params.items() if v}
    params.update({k: str(v) for k, v in changes.items()})
    return f"{request.url.path}?{urlencode(params)}"


templates.env.globals["page_url"] = page_url
