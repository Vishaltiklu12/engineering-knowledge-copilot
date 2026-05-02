import json
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.core.config import get_settings
from app.core.exceptions import ExternalDependencyError, ValidationAppError
from app.models.enums import AnswerStatus
from app.services.openai_client import OpenAICompatibleClient
from app.services.retry import RetryPolicy

if TYPE_CHECKING:
    from app.services.retrieval import RetrievedChunk


@dataclass
class LLMResponse:
    answer: str | None
    answer_status: str
    confidence: float
    follow_up_questions: list[str]
    rejection_reason: str | None = None


class LLMService(ABC):
    model_name: str

    @abstractmethod
    def generate_answer(
        self,
        question: str,
        contexts: list["RetrievedChunk"],
        retrieval_confidence: float,
    ) -> LLMResponse:
        raise NotImplementedError


class PlaceholderLLMService(LLMService):
    """Simple grounded response composer that avoids external dependencies."""

    def __init__(self) -> None:
        self.model_name = get_settings().llm_model

    def generate_answer(
        self,
        question: str,
        contexts: list["RetrievedChunk"],
        retrieval_confidence: float,
    ) -> LLMResponse:
        grounded_statements = [
            self._format_grounded_statement(hit.content, index)
            for index, hit in enumerate(contexts[: min(3, len(contexts))], start=1)
        ]
        answer = " ".join(grounded_statements)

        return LLMResponse(
            answer=answer or f"I could not generate a grounded answer for: {question}",
            answer_status=AnswerStatus.GROUNDED.value,
            confidence=retrieval_confidence,
            follow_up_questions=self._build_follow_up_questions(question, contexts),
        )

    @staticmethod
    def _format_grounded_statement(content: str, citation_index: int) -> str:
        cleaned = " ".join(content.split()).strip()
        if not cleaned:
            return f"[{citation_index}]"
        if cleaned[-1] not in ".!?":
            cleaned = f"{cleaned}."
        return f"{cleaned} [{citation_index}]"

    @staticmethod
    def _build_follow_up_questions(question: str, contexts: list["RetrievedChunk"]) -> list[str]:
        if not contexts:
            return [
                "Would you like to narrow the question to a specific system or component?",
                "Should I show the closest retrieved chunks instead of answering directly?",
            ]

        primary_document = contexts[0].document_name
        questions = [
            f"Do you want a deeper breakdown of the guidance in {primary_document}?",
            "Should I compare the cited chunks and highlight tradeoffs or inconsistencies?",
            f"Would you like me to turn this answer into implementation steps for: {question}?",
        ]
        return questions[:3]


class OpenAILLMService(LLMService):
    _JSON_OBJECT_PATTERN = re.compile(r"\{.*\}", re.DOTALL)
    _CITATION_PATTERN = re.compile(r"\[(\d+)\]")

    def __init__(self, api_client: OpenAICompatibleClient | None = None) -> None:
        settings = get_settings()
        self._settings = settings
        self.model_name = settings.llm_model
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

    def generate_answer(
        self,
        question: str,
        contexts: list["RetrievedChunk"],
        retrieval_confidence: float,
    ) -> LLMResponse:
        response = self._client.post_json(
            path="/chat/completions",
            payload={
                "model": self.model_name,
                "temperature": self._settings.llm_temperature,
                "max_tokens": self._settings.llm_max_output_tokens,
                "response_format": {"type": "json_object"},
                "messages": self._build_messages(question=question, contexts=contexts),
            },
            operation_name="llm completion request",
        )
        content = self._extract_content(response)
        payload = self._parse_payload(content)
        return self._normalize_payload(
            payload=payload,
            question=question,
            contexts=contexts,
            retrieval_confidence=retrieval_confidence,
        )

    @staticmethod
    def _build_messages(question: str, contexts: list["RetrievedChunk"]) -> list[dict[str, str]]:
        context_sections = []
        for index, hit in enumerate(contexts, start=1):
            section = (
                f"[{index}] document={hit.document_name}; section={hit.section_title or 'n/a'}; "
                f"page={hit.page_number if hit.page_number is not None else 'n/a'}; score={hit.score:.4f}\n"
                f"{hit.content.strip()}"
            )
            context_sections.append(section)
        joined_context = "\n\n".join(context_sections)

        return [
            {
                "role": "system",
                "content": (
                    "You are an engineering knowledge assistant. Answer only from the provided retrieved context. "
                    "Every factual statement in the answer must be backed by bracket citations like [1] or [2]. "
                    "If the context is insufficient, set answer to null and answer_status to unsupported. "
                    "Return strict JSON with keys: answer, answer_status, confidence, follow_up_questions, rejection_reason."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Question:\n{question}\n\n"
                    f"Retrieved context:\n{joined_context}\n\n"
                    "Rules:\n"
                    "- Do not use information outside the retrieved context.\n"
                    "- answer_status must be grounded, unsupported, or insufficient_context.\n"
                    "- confidence must be a number between 0 and 1.\n"
                    "- follow_up_questions must be an array of short strings.\n"
                    "- rejection_reason must be null for grounded answers."
                ),
            },
        ]

    def _extract_content(self, response: dict) -> str:
        choices = response.get("choices")
        if not isinstance(choices, list) or not choices:
            raise ExternalDependencyError(
                "LLM completion request returned no choices.",
                details={"provider": "openai"},
            )

        message = choices[0].get("message") if isinstance(choices[0], dict) else None
        if not isinstance(message, dict):
            raise ExternalDependencyError(
                "LLM completion request returned an invalid message payload.",
                details={"provider": "openai"},
            )

        content = message.get("content")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            text_parts = [
                part.get("text", "")
                for part in content
                if isinstance(part, dict) and isinstance(part.get("text"), str)
            ]
            joined = "".join(text_parts).strip()
            if joined:
                return joined

        raise ExternalDependencyError(
            "LLM completion request returned no textual content.",
            details={"provider": "openai"},
        )

    def _parse_payload(self, content: str) -> dict:
        content = content.strip()
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            match = self._JSON_OBJECT_PATTERN.search(content)
            if not match:
                raise ExternalDependencyError(
                    "LLM completion request returned invalid JSON content.",
                    details={"provider": "openai", "content_excerpt": content[:280]},
                )
            try:
                parsed = json.loads(match.group(0))
            except json.JSONDecodeError as exc:
                raise ExternalDependencyError(
                    "LLM completion request returned malformed JSON content.",
                    details={"provider": "openai", "content_excerpt": content[:280]},
                ) from exc

        if not isinstance(parsed, dict):
            raise ExternalDependencyError(
                "LLM completion request returned an unexpected JSON shape.",
                details={"provider": "openai", "parsed_type": type(parsed).__name__},
            )
        return parsed

    def _normalize_payload(
        self,
        *,
        payload: dict,
        question: str,
        contexts: list["RetrievedChunk"],
        retrieval_confidence: float,
    ) -> LLMResponse:
        answer_status = str(payload.get("answer_status") or AnswerStatus.GROUNDED.value).strip().lower()
        if answer_status not in {
            AnswerStatus.GROUNDED.value,
            AnswerStatus.UNSUPPORTED.value,
            AnswerStatus.INSUFFICIENT_CONTEXT.value,
        }:
            answer_status = AnswerStatus.GROUNDED.value if payload.get("answer") else AnswerStatus.UNSUPPORTED.value

        answer = payload.get("answer")
        answer_text = self._normalize_answer(answer if isinstance(answer, str) else None, len(contexts))
        rejection_reason = payload.get("rejection_reason")
        if rejection_reason is not None:
            rejection_reason = " ".join(str(rejection_reason).split()).strip() or None

        confidence = self._normalize_confidence(payload.get("confidence"), retrieval_confidence)
        follow_ups = self._normalize_follow_ups(payload.get("follow_up_questions"), question, contexts)

        if answer_status == AnswerStatus.GROUNDED.value and not answer_text:
            answer_status = AnswerStatus.UNSUPPORTED.value
            rejection_reason = rejection_reason or "The model did not return a grounded answer."

        if answer_status != AnswerStatus.GROUNDED.value:
            answer_text = None
            rejection_reason = rejection_reason or "The available context was not strong enough for a grounded answer."

        return LLMResponse(
            answer=answer_text,
            answer_status=answer_status,
            confidence=confidence,
            follow_up_questions=follow_ups,
            rejection_reason=rejection_reason,
        )

    def _normalize_answer(self, answer: str | None, max_citation_index: int) -> str | None:
        if answer is None:
            return None

        normalized = " ".join(answer.split()).strip()
        if not normalized:
            return None

        normalized = self._CITATION_PATTERN.sub(
            lambda match: match.group(0) if 1 <= int(match.group(1)) <= max_citation_index else "",
            normalized,
        )
        normalized = re.sub(r"\s{2,}", " ", normalized).strip()

        valid_citations = self._CITATION_PATTERN.findall(normalized)
        if not valid_citations and max_citation_index > 0:
            if normalized[-1] not in ".!?":
                normalized = f"{normalized}."
            references = " ".join(f"[{index}]" for index in range(1, min(max_citation_index, 2) + 1))
            normalized = f"{normalized} {references}".strip()
        return normalized

    @staticmethod
    def _normalize_confidence(value: object, retrieval_confidence: float) -> float:
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            parsed = retrieval_confidence

        parsed = max(0.0, min(1.0, parsed))
        return round(min(parsed, retrieval_confidence), 4)

    @staticmethod
    def _normalize_follow_ups(
        value: object,
        question: str,
        contexts: list["RetrievedChunk"],
    ) -> list[str]:
        if isinstance(value, list):
            follow_ups: list[str] = []
            for item in value:
                if not isinstance(item, str):
                    continue
                normalized = " ".join(item.split()).strip()
                if not normalized or normalized in follow_ups:
                    continue
                follow_ups.append(normalized)
                if len(follow_ups) == 3:
                    return follow_ups
            if follow_ups:
                return follow_ups

        if not contexts:
            return [
                "Would you like to narrow the question to a specific system or component?",
                "Should I show the closest retrieved chunks instead of answering directly?",
            ]

        primary_document = contexts[0].document_name
        return [
            f"Do you want a deeper breakdown of the guidance in {primary_document}?",
            "Should I compare the cited chunks and highlight tradeoffs or inconsistencies?",
            f"Would you like me to turn this answer into implementation steps for: {question}?",
        ]


def get_llm_service() -> LLMService:
    settings = get_settings()

    if settings.llm_provider == "placeholder":
        return PlaceholderLLMService()
    if settings.llm_provider == "openai":
        return OpenAILLMService()

    raise ValidationAppError(
        "Unsupported LLM provider configured.",
        details={"llm_provider": settings.llm_provider},
    )
