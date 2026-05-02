import uuid

from app.schemas.query import CitationData, QueryData
from app.services.query_history import QueryHistoryService


class FakeSession:
    def __init__(self) -> None:
        self.added: list[object] = []
        self.committed = False

    def add(self, obj: object) -> None:
        self.added.append(obj)

    def flush(self) -> None:
        for obj in self.added:
            if hasattr(obj, "id") and getattr(obj, "id", None) is None:
                setattr(obj, "id", uuid.uuid4())

    def commit(self) -> None:
        self.committed = True


def test_query_history_service_records_output_and_citations() -> None:
    session = FakeSession()
    knowledge_base_id = uuid.uuid4()
    document_id = uuid.uuid4()
    chunk_id = uuid.uuid4()

    query_data = QueryData(
        query_id=uuid.uuid4(),
        answer_status="grounded",
        answer="Use a worker queue. [1]",
        citations=[
            CitationData(
                citation_id=1,
                document_id=document_id,
                document_name="architecture.md",
                chunk_id=chunk_id,
                snippet="Use a worker queue.",
                page=1,
                score=0.94,
            )
        ],
        confidence=0.94,
        follow_up_questions=["Do you want implementation steps next?"],
    )

    query_log = QueryHistoryService().record(
        session=session,
        knowledge_base_id=knowledge_base_id,
        question="How should ingestion work?",
        query_data=query_data,
        cache_hit=False,
        latency_ms=123,
    )

    assert query_log.knowledge_base_id == knowledge_base_id
    assert query_log.answer_json["answer"] == "Use a worker queue. [1]"
    assert query_log.answer_json["confidence"] == 0.94
    assert query_log.answer_json["follow_up_questions"] == ["Do you want implementation steps next?"]
    assert session.committed is True
    assert len(session.added) == 2
