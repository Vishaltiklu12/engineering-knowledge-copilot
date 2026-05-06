import logging
from dataclasses import dataclass
from typing import Any

import httpx

from app.core.exceptions import ExternalDependencyError, ValidationAppError
from app.services.retry import RetryPolicy, RetryService

logger = logging.getLogger(__name__)

_RETRYABLE_STATUS_CODES = {408, 409, 425, 429, 500, 502, 503, 504}


@dataclass
class RetryableProviderError(Exception):
    message: str
    status_code: int | None = None
    response_excerpt: str | None = None

    def __str__(self) -> str:
        return self.message


class OpenAICompatibleClient:
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        timeout_seconds: int,
        retry_policy: RetryPolicy,
        organization: str | None = None,
        project: str | None = None,
        retry_service: RetryService | None = None,
        http_client: httpx.Client | None = None,
    ) -> None:
        if not api_key.strip():
            raise ValidationAppError("An API key is required for the configured model provider.")
        if not base_url.strip():
            raise ValidationAppError("A base URL is required for the configured model provider.")

        self._retry_policy = retry_policy
        self._retry_service = retry_service or RetryService()
        self._base_url = base_url.rstrip("/")
        self._client = http_client or httpx.Client(
            base_url=self._base_url,
            timeout=timeout_seconds,
            headers=self._build_headers(
                api_key=api_key,
                organization=organization,
                project=project,
            ),
        )

    @staticmethod
    def _build_headers(
        *,
        api_key: str,
        organization: str | None,
        project: str | None,
    ) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        if organization:
            headers["OpenAI-Organization"] = organization
        if project:
            headers["OpenAI-Project"] = project
        return headers

    def post_json(self, *, path: str, payload: dict[str, Any], operation_name: str) -> dict[str, Any]:
        def operation() -> dict[str, Any]:
            try:
                response = self._client.post(path, json=payload)
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                raise RetryableProviderError(
                    message=f"{operation_name} failed before a response was received.",
                ) from exc

            if response.status_code in _RETRYABLE_STATUS_CODES:
                raise RetryableProviderError(
                    message=f"{operation_name} returned a retryable status code.",
                    status_code=response.status_code,
                    response_excerpt=self._excerpt(response.text),
                )

            if response.is_error:
                raise ExternalDependencyError(
                    f"{operation_name} failed.",
                    details={
                        "provider": "openai",
                        "status_code": response.status_code,
                        "response_excerpt": self._excerpt(response.text),
                    },
                )

            try:
                response_payload = response.json()
            except ValueError as exc:
                raise ExternalDependencyError(
                    f"{operation_name} returned a non-JSON response.",
                    details={
                        "provider": "openai",
                        "status_code": response.status_code,
                        "response_excerpt": self._excerpt(response.text),
                    },
                ) from exc

            if not isinstance(response_payload, dict):
                raise ExternalDependencyError(
                    f"{operation_name} returned an unexpected response shape.",
                    details={"provider": "openai", "response_type": type(response_payload).__name__},
                )
            return response_payload

        try:
            return self._retry_service.run(
                operation,
                retryable_exceptions=(RetryableProviderError,),
                policy=self._retry_policy,
                operation_name=operation_name,
            )
        except RetryableProviderError as exc:
            logger.exception("%s failed after retries.", operation_name)
            raise ExternalDependencyError(
                f"{operation_name} failed after retries.",
                details={
                    "provider": "openai",
                    "status_code": exc.status_code,
                    "response_excerpt": exc.response_excerpt,
                },
            ) from exc

    @staticmethod
    def _excerpt(text: str, limit: int = 280) -> str:
        normalized = " ".join((text or "").split())
        return normalized[:limit]
