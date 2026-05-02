from fastapi import APIRouter
from fastapi.responses import JSONResponse, Response
from redis import Redis
from redis.exceptions import RedisError
from sqlalchemy import text

from app.core.config import get_settings
from app.db.session import engine
from app.services.metrics import CONTENT_TYPE_LATEST, render_metrics

router = APIRouter(tags=["health"])


@router.get("/healthz")
def healthz() -> dict:
    return {"status": "ok"}


@router.get("/readyz")
def readyz():
    settings = get_settings()

    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception:
        return JSONResponse(
            status_code=503,
            content={"status": "degraded", "database": False, "redis": False},
        )

    redis_ok = False
    try:
        redis_ok = bool(Redis.from_url(settings.redis_url).ping())
    except RedisError:
        redis_ok = False

    if not redis_ok:
        return JSONResponse(
            status_code=503,
            content={"status": "degraded", "database": True, "redis": False},
        )

    return {"status": "ready", "database": True, "redis": True}


@router.get("/metrics", include_in_schema=False)
def metrics() -> Response:
    return Response(content=render_metrics(), media_type=CONTENT_TYPE_LATEST)
