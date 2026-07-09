"""FastAPI application factory."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from laia.api.assistant import router as assistant_router
from laia.api.events import router as events_router
from laia.api.health import router as health_router
from laia.config import get_settings
from laia.logging_config import new_request_id, request_id_var, setup_logging

logger = logging.getLogger(__name__)


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get("X-Request-ID") or new_request_id()
        token = request_id_var.set(request_id)
        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            request_id_var.reset(token)


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    settings = get_settings()
    logger.info("LAIA API starting timezone=%s", settings.laia_timezone)
    yield
    logger.info("LAIA API shutting down")


def create_app() -> FastAPI:
    app = FastAPI(
        title="LAIA",
        description="Local AI Assistant — calendar MVP",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.add_middleware(RequestIdMiddleware)
    app.include_router(events_router)
    app.include_router(assistant_router)
    app.include_router(health_router)

    @app.get("/healthz", tags=["health"])
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
