import uuid

from app.models.enums import AnswerStatus
from app.schemas.query import CitationData
from app.services.llm import LLMResponse, LLMService, PlaceholderLLMService
from app.services.rag import RagService
from app.services.retrieval import RetrievedChunk, RetrievalResult


class FakeRetrievalService:
    def __init__(self, result: RetrievalResult) -> None:
        self.result = result

    def retrieve(self, session, knowledge_base_id: uuid.UUID, question: str, top_k: int) -> RetrievalResult:
        return self.result


class FakeLLMService(LLMService):
    model_name = "fake-llm"

    def generate_answer(self, question: str, contexts: list[RetrievedChunk], retrieval_confidence: float) -> LLMResponse:
        return LLMResponse(
            answer="Use a worker-backed ingestion pipeline. [1]",
            answer_status=AnswerStatus.GROUNDED.value,
            confidence=retrieval_confidence,
            follow_up_questions=["Do you want the implementation steps next?"],
        )


def build_hit(score: float = 0.91) -> RetrievedChunk:
    return RetrievedChunk(
        document_id=uuid.uuid4(),
        document_name="architecture.md",
        chunk_id=uuid.uuid4(),
        chunk_index=0,
        content="Use a worker-backed ingestion pipeline to keep uploads responsive.",
        page_number=1,
        section_title="Ingestion",
        metadata={"chunking_strategy": "sliding_window"},
        score=score,
    )


def build_citation(hit: RetrievedChunk) -> CitationData:
    return CitationData(
        citation_id=1,
        document_id=hit.document_id,
        document_name=hit.document_name,
        chunk_id=hit.chunk_id,
        snippet=hit.content[:240],
        page=hit.page_number,
        score=hit.score,
    )


def test_placeholder_llm_returns_structured_grounded_output() -> None:
    hit = build_hit(score=0.92)
    response = PlaceholderLLMService().generate_answer(
        question="How should ingestion work?",
        contexts=[hit],
        retrieval_confidence=0.92,
    )

    assert response.answer is not None
    assert "[1]" in response.answer
    assert response.answer_status == AnswerStatus.GROUNDED.value
    assert response.confidence == 0.92
    assert len(response.follow_up_questions) >= 1


def test_rag_service_rejects_low_confidence_answers() -> None:
    hit = build_hit(score=0.31)
    retrieval_result = RetrievalResult(
        question="How should ingestion work?",
        top_k=3,
        embedding_model="fake-embedding",
        confidence=0.31,
        hits=[hit],
        citations=[build_citation(hit)],
    )
    rag = RagService(
        llm_service=FakeLLMService(),
        retrieval_service=FakeRetrievalService(retrieval_result),
    )

    query_data, hits = rag.answer(
        session=object(),
        knowledge_base_id=uuid.uuid4(),
        question="How should ingestion work?",
        top_k=3,
    )

    assert len(hits) == 1
    assert query_data.answer is None
    assert query_data.answer_status == AnswerStatus.UNSUPPORTED.value
    assert query_data.confidence == 0.31
    assert query_data.rejection_reason is not None
    assert len(query_data.follow_up_questions) >= 1
