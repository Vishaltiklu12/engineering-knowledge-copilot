import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from app.core.exceptions import AppException

logger = logging.getLogger(__name__)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppException)
    async def handle_app_exception(request: Request, exc: AppException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "data": None,
                "meta": {"request_id": getattr(request.state, "request_id", "req_error")},
                "error": {
                    "code": exc.error_code,
                    "message": exc.message,
                    "details": exc.details,
                },
            },
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def handle_request_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "data": None,
                "meta": {"request_id": getattr(request.state, "request_id", "req_error")},
                "error": {
                    "code": "request_validation_error",
                    "message": "Request validation failed.",
                    "details": {"errors": exc.errors()},
                },
            },
        )

    @app.exception_handler(IntegrityError)
    async def handle_integrity_error(request: Request, exc: IntegrityError) -> JSONResponse:
        logger.warning("Database integrity error: %s", exc)
        return JSONResponse(
            status_code=409,
            content={
                "data": None,
                "meta": {"request_id": getattr(request.state, "request_id", "req_error")},
                "error": {
                    "code": "database_conflict",
                    "message": "The request could not be completed because of a database constraint.",
                    "details": {"error_type": type(exc).__name__},
                },
            },
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_exception(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled exception")
        return JSONResponse(
            status_code=500,
            content={
                "data": None,
                "meta": {"request_id": getattr(request.state, "request_id", "req_error")},
                "error": {
                    "code": "internal_server_error",
                    "message": "Unexpected server error.",
                    "details": {"error_type": type(exc).__name__},
                },
            },
        )
