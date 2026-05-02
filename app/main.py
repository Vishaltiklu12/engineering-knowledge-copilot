import logging
import uuid
from contextlib import asynccontextmanager
from time import perf_counter

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import OperationalError

import app.models  # noqa: F401
from app.api.errors import register_exception_handlers
from app.api.router import api_router
from app.core.config import get_cors_origins, get_settings
from app.core.logging import setup_logging
from app.db.base import Base
from app.db.session import engine
from app.services.metrics import observe_http_request

settings = get_settings()
setup_logging(settings.log_level)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    if settings.auto_create_schema:
        try:
            Base.metadata.create_all(bind=engine)
        except OperationalError:
            if settings.require_database_on_startup:
                raise
            logger.warning("database_unavailable_during_startup")
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)
register_exception_handlers(app)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(settings),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_context_middleware(request: Request, call_next):
    request_id = f"req_{uuid.uuid4().hex[:12]}"
    request.state.request_id = request_id
    started_at = perf_counter()

    response = await call_next(request)

    duration_seconds = perf_counter() - started_at
    latency_ms = int(duration_seconds * 1000)
    route = request.scope.get("route")
    path_template = getattr(route, "path", request.url.path)

    response.headers["X-Request-ID"] = request_id
    if hasattr(request.state, "rate_limit"):
        rate_limit = request.state.rate_limit
        response.headers["X-RateLimit-Limit"] = str(rate_limit.limit)
        response.headers["X-RateLimit-Remaining"] = str(rate_limit.remaining)
        response.headers["X-RateLimit-Reset"] = str(rate_limit.reset_in_seconds)

    observe_http_request(
        method=request.method,
        path=path_template,
        status_code=response.status_code,
        duration_seconds=duration_seconds,
    )
    logger.info(
        "request_completed",
        extra={
            "request_id": request_id,
            "method": request.method,
            "path": path_template,
            "latency_ms": latency_ms,
            "status_code": response.status_code,
        },
    )
    response.headers["X-Response-Time-Ms"] = str(latency_ms)
    return response


app.include_router(api_router)
