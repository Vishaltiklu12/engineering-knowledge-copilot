class AppException(Exception):
    status_code = 400
    error_code = "app_error"

    def __init__(
        self,
        message: str,
        details: dict | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}
        self.headers = headers or {}


class NotFoundError(AppException):
    status_code = 404
    error_code = "not_found"


class ConflictError(AppException):
    status_code = 409
    error_code = "conflict"


class ValidationAppError(AppException):
    status_code = 422
    error_code = "validation_error"


class ExternalDependencyError(AppException):
    status_code = 503
    error_code = "external_dependency_unavailable"


class RateLimitExceededError(AppException):
    status_code = 429
    error_code = "rate_limit_exceeded"

    def __init__(self, message: str, details: dict | None = None, retry_after_seconds: int | None = None) -> None:
        headers = {}
        if retry_after_seconds is not None:
            headers["Retry-After"] = str(retry_after_seconds)
        super().__init__(message=message, details=details, headers=headers)
