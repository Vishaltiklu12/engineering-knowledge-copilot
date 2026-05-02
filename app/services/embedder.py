import hashlib
import math
from abc import ABC, abstractmethod

from app.core.config import get_settings
from app.core.exceptions import ExternalDependencyError, ValidationAppError
from app.services.openai_client import OpenAICompatibleClient
from app.services.retry import RetryPolicy


class EmbeddingService(ABC):
    model_name: str
    dimensions: int

    @abstractmethod
    def embed_text(self, text: str) -> list[float]:
        raise NotImplementedError

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_text(text) for text in texts]


class PlaceholderEmbeddingService(EmbeddingService):
    """Deterministic local embeddings for development and portfolio demos."""

    def __init__(self) -> None:
        settings = get_settings()
        self.dimensions = settings.embedding_dimensions
        self.model_name = settings.embedding_model

    def embed_text(self, text: str) -> list[float]:
        values: list[float] = []
        seed = (text or " ").encode("utf-8")
        counter = 0

        while len(values) < self.dimensions:
            digest = hashlib.sha256(seed + counter.to_bytes(4, "big")).digest()
            for index in range(0, len(digest), 2):
                segment = digest[index : index + 2]
                if len(segment) < 2:
                    continue
                number = int.from_bytes(segment, "big")
                values.append((number / 65535.0) * 2 - 1)
                if len(values) == self.dimensions:
                    break
            counter += 1

        norm = math.sqrt(sum(value * value for value in values)) or 1.0
        return [value / norm for value in values]


class OpenAIEmbeddingService(EmbeddingService):
    def __init__(self, api_client: OpenAICompatibleClient | None = None) -> None:
        settings = get_settings()
        self.dimensions = settings.embedding_dimensions
        self.model_name = settings.embedding_model
        self._client = api_client or OpenAICompatibleClient(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
            timeout_seconds=settings.model_request_timeout_seconds,
            organization=settings.openai_organization or None,
            project=settings.openai_project or None,
            retry_policy=RetryPolicy(
                attempts=settings.model_retry_attempts,
                delay_seconds=settings.model_retry_delay_seconds,
                backoff_multiplier=settings.model_retry_backoff_multiplier,
            ),
        )

    def embed_text(self, text: str) -> list[float]:
        return self.embed_texts([text])[0]

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        payload = {
            "model": self.model_name,
            "input": [self._normalize_text(text) for text in texts],
            "dimensions": self.dimensions,
        }
        response = self._client.post_json(
            path="/embeddings",
            payload=payload,
            operation_name="embedding request",
        )
        data = response.get("data")
        if not isinstance(data, list) or len(data) != len(texts):
            raise ExternalDependencyError(
                "Embedding request returned an unexpected result count.",
                details={
                    "provider": "openai",
                    "expected_count": len(texts),
                    "returned_count": len(data) if isinstance(data, list) else None,
                },
            )

        embeddings: list[list[float]] = []
        for item in data:
            vector = item.get("embedding") if isinstance(item, dict) else None
            embeddings.append(self._validate_embedding(vector))
        return embeddings

    @staticmethod
    def _normalize_text(text: str) -> str:
        normalized = " ".join((text or "").split()).strip()
        return normalized or " "

    def _validate_embedding(self, embedding: object) -> list[float]:
        if not isinstance(embedding, list) or not embedding:
            raise ExternalDependencyError(
                "Embedding request returned an invalid embedding payload.",
                details={"provider": "openai"},
            )

        try:
            vector = [float(value) for value in embedding]
        except (TypeError, ValueError) as exc:
            raise ExternalDependencyError(
                "Embedding request returned non-numeric embedding values.",
                details={"provider": "openai"},
            ) from exc

        if len(vector) != self.dimensions:
            raise ExternalDependencyError(
                "Embedding dimensions did not match the configured pgvector dimensions.",
                details={
                    "provider": "openai",
                    "expected_dimensions": self.dimensions,
                    "received_dimensions": len(vector),
                },
            )
        return vector


def get_embedding_service() -> EmbeddingService:
    settings = get_settings()

    if settings.embedding_provider == "placeholder":
        return PlaceholderEmbeddingService()
    if settings.embedding_provider == "openai":
        return OpenAIEmbeddingService()

    raise ValidationAppError(
        "Unsupported embedding provider configured.",
        details={"embedding_provider": settings.embedding_provider},
    )
