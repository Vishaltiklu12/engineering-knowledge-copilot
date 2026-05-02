import json
import uuid
from types import SimpleNamespace

from app.models.enums import AnswerStatus
from app.services.embedder import OpenAIEmbeddingService
from app.services.llm import OpenAILLMService
from app.services.retrieval import RetrievedChunk


class FakeProviderClient:
    def __init__(self, response: dict) -> None:
        self.response = response
        self.calls: list[dict] = []

    def post_json(self, *, path: str, payload: dict, operation_name: str) -> dict:
        self.calls.append(
            {
                "path": path,
                "payload": payload,
                "operation_name": operation_name,
            }
        )
        return self.response


def build_hit(index: int = 1, score: float = 0.91) -> RetrievedChunk:
    return RetrievedChunk(
        document_id=uuid.uuid4(),
        document_name="architecture.md",
        chunk_id=uuid.uuid4(),
        chunk_index=index,
        content="Use a worker-backed ingestion pipeline to keep uploads responsive.",
        page_number=1,
        section_title="Ingestion",
        metadata={"chunking_strategy": "sliding_window"},
        score=score,
    )


def test_openai_embedding_service_batches_inputs(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.embedder.get_settings",
        lambda: SimpleNamespace(
            embedding_dimensions=3,
            embedding_model="text-embedding-3-small",
            openai_api_key="",
            openai_base_url="",
            openai_organization="",
            openai_project="",
            model_request_timeout_seconds=45,
            model_retry_attempts=3,
            model_retry_delay_seconds=0.5,
            model_retry_backoff_multiplier=2.0,
        ),
    )
    client = FakeProviderClient(
        {
            "data": [
                {"embedding": [0.1, 0.2, 0.3]},
                {"embedding": [0.4, 0.5, 0.6]},
            ]
        }
    )

    result = OpenAIEmbeddingService(api_client=client).embed_texts(["First chunk", "   "])

    assert result == [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
    assert client.calls[0]["path"] == "/embeddings"
    assert client.calls[0]["payload"]["dimensions"] == 3
    assert client.calls[0]["payload"]["input"] == ["First chunk", " "]


def test_openai_llm_service_normalizes_citations_and_confidence(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.llm.get_settings",
        lambda: SimpleNamespace(
            llm_model="gpt-4.1-mini",
            llm_temperature=0.1,
            llm_max_output_tokens=500,
            openai_api_key="",
            openai_base_url="",
            openai_organization="",
            openai_project="",
            model_request_timeout_seconds=45,
            model_retry_attempts=3,
            model_retry_delay_seconds=0.5,
            model_retry_backoff_multiplier=2.0,
        ),
    )
    client = FakeProviderClient(
        {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "answer": "Use worker-based ingestion for uploads [1] [4]",
                                "answer_status": "grounded",
                                "confidence": 0.99,
                                "follow_up_questions": [
                                    "Do you want implementation steps next?",
                                    "Do you want implementation steps next?",
                                    42,
                                ],
                                "rejection_reason": None,
                            }
                        )
                    }
                }
            ]
        }
    )

    response = OpenAILLMService(api_client=client).generate_answer(
        question="How should ingestion work?",
        contexts=[build_hit(index=0), build_hit(index=1)],
        retrieval_confidence=0.87,
    )

    assert response.answer == "Use worker-based ingestion for uploads [1]"
    assert response.answer_status == AnswerStatus.GROUNDED.value
    assert response.confidence == 0.87
    assert response.follow_up_questions == ["Do you want implementation steps next?"]
    assert client.calls[0]["path"] == "/chat/completions"


def test_openai_llm_service_falls_back_to_unsupported_without_answer(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.llm.get_settings",
        lambda: SimpleNamespace(
            llm_model="gpt-4.1-mini",
            llm_temperature=0.1,
            llm_max_output_tokens=500,
            openai_api_key="",
            openai_base_url="",
            openai_organization="",
            openai_project="",
            model_request_timeout_seconds=45,
            model_retry_attempts=3,
            model_retry_delay_seconds=0.5,
            model_retry_backoff_multiplier=2.0,
        ),
    )
    client = FakeProviderClient(
        {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "answer": None,
                                "answer_status": "grounded",
                                "confidence": 0.42,
                                "follow_up_questions": [],
                                "rejection_reason": None,
                            }
                        )
                    }
                }
            ]
        }
    )

    response = OpenAILLMService(api_client=client).generate_answer(
        question="How should ingestion work?",
        contexts=[build_hit()],
        retrieval_confidence=0.42,
    )

    assert response.answer is None
    assert response.answer_status == AnswerStatus.UNSUPPORTED.value
    assert response.rejection_reason == "The model did not return a grounded answer."
    assert len(response.follow_up_questions) >= 1
