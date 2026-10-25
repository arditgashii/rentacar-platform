from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from starlette.exceptions import HTTPException as StarletteHTTPException


class AppError(Exception):
    """A business error with an HTTP status and a stable machine-readable code."""

    def __init__(self, status: int, code: str, detail: str) -> None:
        super().__init__(detail)
        self.status = status
        self.code = code
        self.detail = detail


def not_found(what: str) -> AppError:
    return AppError(404, f"{what.upper()}_NOT_FOUND", f"{what.capitalize()} not found.")


def forbidden(detail: str = "You are not allowed to do this.") -> AppError:
    return AppError(403, "FORBIDDEN", detail)


_STATUS_CODES = {
    400: "BAD_REQUEST",
    401: "NOT_AUTHENTICATED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
    409: "CONFLICT",
    413: "PAYLOAD_TOO_LARGE",
}

# Renders an error as an HTML page for the web UI: (request, status, message) -> response.
HtmlErrorPage = Callable[[Request, int, str], Awaitable[Response]]


def _is_api(request: Request) -> bool:
    return request.url.path.startswith(("/api/", "/health", "/media/", "/metrics"))


def _error(status: int, code: str, detail: object) -> JSONResponse:
    return JSONResponse(status_code=status, content={"detail": detail, "code": code})


def register_error_handlers(app: FastAPI, html_error_page: HtmlErrorPage) -> None:
    @app.exception_handler(AppError)
    async def app_error(request: Request, exc: AppError) -> Response:
        if _is_api(request):
            return _error(exc.status, exc.code, exc.detail)
        return await html_error_page(request, exc.status, exc.detail)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError) -> Response:
        problems = [
            f"{'.'.join(str(part) for part in error['loc'] if part != 'body')}: {error['msg']}"
            for error in exc.errors()
        ]
        if _is_api(request):
            return _error(422, "VALIDATION_ERROR", "; ".join(problems))
        return await html_error_page(request, 404, "Page not found.")

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, exc: StarletteHTTPException) -> Response:
        if _is_api(request):
            return _error(exc.status_code, _STATUS_CODES.get(exc.status_code, "ERROR"), exc.detail)
        message = "Page not found." if exc.status_code == 404 else str(exc.detail)
        return await html_error_page(request, exc.status_code, message)
