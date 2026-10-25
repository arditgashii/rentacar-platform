"""JSON logs with a request id, Prometheus metrics and optional OpenTelemetry tracing."""

import json
import logging
import re
import time
import uuid
from contextvars import ContextVar

from fastapi import FastAPI, Request, Response
from prometheus_fastapi_instrumentator import Instrumentator
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from app.config import get_settings

request_id: ContextVar[str] = ContextVar("request_id", default="-")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "time": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": request_id.get(),
        }
        for key in ("method", "path", "status", "duration_ms"):
            if hasattr(record, key):
                entry[key] = getattr(record, key)
        if record.exc_info:
            entry["error"] = self.formatException(record.exc_info)
        return json.dumps(entry)


def setup_logging() -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.INFO)
    # Uvicorn's access log would repeat every request; ours has the request id and duration.
    logging.getLogger("uvicorn.access").disabled = True
    logging.getLogger("azure").setLevel(logging.WARNING)


access_log = logging.getLogger("drivenow.access")


SAFE_REQUEST_ID = re.compile(r"^[A-Za-z0-9-]{1,64}$")


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # A caller's id is kept only when it is safe to write into a log line.
        sent = request.headers.get("X-Request-ID", "")
        token = request_id.set(sent if SAFE_REQUEST_ID.match(sent) else uuid.uuid4().hex[:16])
        started = time.perf_counter()
        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id.get()
            if not request.url.path.startswith(("/static", "/metrics", "/health")):
                access_log.info(
                    "request",
                    extra={
                        "method": request.method,
                        "path": request.url.path,
                        "status": response.status_code,
                        "duration_ms": round((time.perf_counter() - started) * 1000, 1),
                    },
                )
            return response
        finally:
            request_id.reset(token)


def setup_tracing(app: FastAPI) -> None:
    endpoint = get_settings().otel_exporter_otlp_endpoint
    if not endpoint:
        return
    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    from app.db import engine

    provider = TracerProvider(resource=Resource.create({"service.name": "drivenow-api"}))
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=f"{endpoint}/v1/traces")))
    trace.set_tracer_provider(provider)
    FastAPIInstrumentor.instrument_app(app)
    SQLAlchemyInstrumentor().instrument(engine=engine.sync_engine)


def setup_observability(app: FastAPI) -> None:
    app.add_middleware(RequestIdMiddleware)
    Instrumentator(excluded_handlers=["/metrics", "/health.*", "/static.*", "/media.*"]).instrument(
        app
    ).expose(app, include_in_schema=False)
    setup_tracing(app)
