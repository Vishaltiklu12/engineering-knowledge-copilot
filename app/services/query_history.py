import json
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.query_log import QueryCitation, QueryLog
from app.schemas.query import QueryData, QueryHistoryItemData
from app.services.pagination import PaginationResult, PaginationService


class QueryHistoryService:
    def __init__(self, pagination_service: PaginationService | None = None) -> None:
        self.pagination_service = pagination_service or PaginationService()

    def record(
        self,
        session: Session,
        knowledge_base_id: uuid.UUID,
        question: str,
        query_data: QueryData,
        cache_hit: bool,
        latency_ms: int,
    ) -> QueryLog:
        query_log = QueryLog(
            knowledge_base_id=knowledge_base_id,
            question=question,
            normalized_question=question.strip().lower(),
            answer_json=json.loads(query_data.model_dump_json()),
            cache_hit=cache_hit,
            latency_ms=latency_ms,
        )
        session.add(query_log)
        session.flush()

        for citation in query_data.citations:
            session.add(
                QueryCitation(
                    query_log_id=query_log.id,
                    chunk_id=citation.chunk_id,
                    rank=citation.citation_id,
                    score=citation.score,
                )
            )

        session.commit()
        return query_log

    def list_history(
        self,
        session: Session,
        *,
        knowledge_base_id: uuid.UUID | None,
        page: int,
        page_size: int,
    ) -> PaginationResult[QueryHistoryItemData]:
        filters = []
        if knowledge_base_id is not None:
            filters.append(QueryLog.knowledge_base_id == knowledge_base_id)

        total_items = session.execute(select(func.count()).select_from(QueryLog).where(*filters)).scalar_one()
        query_logs = session.scalars(
            select(QueryLog)
            .where(*filters)
            .order_by(QueryLog.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()

        items = [self._serialize_item(query_log) for query_log in query_logs]
        return self.pagination_service.build_result(
            items=items,
            page=page,
            page_size=page_size,
            total_items=total_items,
        )

    @staticmethod
    def _serialize_item(query_log: QueryLog) -> QueryHistoryItemData:
        answer_payload = query_log.answer_json or {}
        answer_preview = answer_payload.get("answer")
        if answer_preview:
            answer_preview = answer_preview[:280]

        return QueryHistoryItemData(
            id=query_log.id,
            knowledge_base_id=query_log.knowledge_base_id,
            question=query_log.question,
            answer_status=str(answer_payload.get("answer_status", "unknown")),
            answer_preview=answer_preview,
            confidence=float(answer_payload.get("confidence", 0.0)),
            citations_count=len(answer_payload.get("citations", [])),
            cache_hit=query_log.cache_hit,
            latency_ms=query_log.latency_ms,
            created_at=query_log.created_at,
        )
