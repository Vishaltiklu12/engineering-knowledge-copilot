import uuid

from app.core.config import get_settings
from app.models.enums import AnswerStatus
from app.schemas.query import QueryData
from app.services.llm import LLMService, get_llm_service
from app.services.retrieval import RetrievalPipelineService, RetrievedChunk


class RagService:
    def __init__(
        self,
        llm_service: LLMService | None = None,
        retrieval_service: RetrievalPipelineService | None = None,
    ) -> None:
        self.settings = get_settings()
        self.retrieval = retrieval_service or RetrievalPipelineService()
        self.llm_service = llm_service or get_llm_service()

    def answer(
        self,
        session,
        knowledge_base_id: uuid.UUID,
        question: str,
        top_k: int,
        include_debug: bool = False,
    ) -> tuple[QueryData, list[RetrievedChunk]]:
        retrieval_result = self.retrieval.retrieve(session, knowledge_base_id, question, top_k=top_k)

        if not retrieval_result.hits:
            return (
                self._build_rejection_response(
                    answer_status=AnswerStatus.INSUFFICIENT_CONTEXT.value,
                    confidence=retrieval_result.confidence,
                    citations=retrieval_result.citations,
                    reason="No indexed chunks were retrieved for this question.",
                    include_debug=include_debug,
                    retrieval_result=retrieval_result,
                ),
                retrieval_result.hits,
            )

        if retrieval_result.confidence < self.settings.grounded_answer_min_confidence:
            return (
                self._build_rejection_response(
                    answer_status=AnswerStatus.UNSUPPORTED.value,
                    confidence=retrieval_result.confidence,
                    citations=retrieval_result.citations,
                    reason="Retrieved evidence did not meet the minimum confidence threshold for a grounded answer.",
                    include_debug=include_debug,
                    retrieval_result=retrieval_result,
                ),
                retrieval_result.hits,
            )

        llm_response = self.llm_service.generate_answer(
            question=question,
            contexts=retrieval_result.hits,
            retrieval_confidence=retrieval_result.confidence,
        )

        debug = None
        if include_debug:
            debug = {
                "retrieved_chunks": len(retrieval_result.hits),
                "scores": [round(hit.score, 4) for hit in retrieval_result.hits],
                "llm_model": self.llm_service.model_name,
                "embedding_model": retrieval_result.embedding_model,
                "retrieval_confidence": retrieval_result.confidence,
                "grounded_answer_min_confidence": self.settings.grounded_answer_min_confidence,
            }

        return (
            QueryData(
                query_id=uuid.uuid4(),
                answer_status=llm_response.answer_status,
                answer=llm_response.answer,
                citations=retrieval_result.citations,
                confidence=llm_response.confidence,
                follow_up_questions=llm_response.follow_up_questions,
                rejection_reason=llm_response.rejection_reason,
                debug=debug,
            ),
            retrieval_result.hits,
        )

    def _build_rejection_response(
        self,
        answer_status: str,
        confidence: float,
        citations,
        reason: str,
        include_debug: bool,
        retrieval_result,
    ) -> QueryData:
        debug = None
        if include_debug:
            debug = {
                "retrieved_chunks": len(retrieval_result.hits),
                "scores": [round(hit.score, 4) for hit in retrieval_result.hits],
                "embedding_model": retrieval_result.embedding_model,
                "retrieval_confidence": retrieval_result.confidence,
                "grounded_answer_min_confidence": self.settings.grounded_answer_min_confidence,
            }

        return QueryData(
            query_id=uuid.uuid4(),
            answer_status=answer_status,
            answer=None,
            citations=citations,
            confidence=confidence,
            follow_up_questions=self._build_rejection_follow_ups(retrieval_result.hits),
            rejection_reason=reason,
            debug=debug,
        )

    @staticmethod
    def _build_rejection_follow_ups(hits: list[RetrievedChunk]) -> list[str]:
        if not hits:
            return [
                "Would you like to upload more documents that cover this topic?",
                "Should I try a narrower question with more specific engineering terms?",
            ]

        primary_document = hits[0].document_name
        return [
            f"Should I show the top retrieved chunks from {primary_document} instead of answering directly?",
            "Would you like me to narrow the question to a subsystem, API, or service boundary?",
            "Should I compare only the highest-scoring cited chunks for stronger grounding?",
        ]
