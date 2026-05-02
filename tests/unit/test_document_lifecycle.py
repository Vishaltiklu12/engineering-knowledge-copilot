import uuid
from types import SimpleNamespace

import pytest

from app.api.v1.query import build_cache_key
from app.core.exceptions import ValidationAppError
from app.models.chunk import ChunkEmbedding, DocumentChunk
from app.models.document import Document
from app.models.enums import DocumentStatus, JobStatus
from app.models.ingestion_job import IngestionJob
from app.models.knowledge_base import KnowledgeBase
from app.models.mixins import utcnow
from app.services.chunker import ChunkPayload, ChunkingStrategy
from app.services.embedder import EmbeddingService
from app.services.ingestion import IngestionService
from app.services.parser import ParsedDocument, ParsedPage


class FakeScalarResult:
    def __init__(self, items: list[object]) -> None:
        self.items = items

    def all(self) -> list[object]:
        return list(self.items)


class FakeSession:
    def __init__(self, *, document: object, job: object, knowledge_base: object) -> None:
        self.document = document
        self.job = job
        self.knowledge_base = knowledge_base
        self.added: list[object] = []
        self.deleted: list[object] = []
        self.commits = 0
        self.rollbacks = 0

    def get(self, model: type[object], object_id: uuid.UUID) -> object | None:
        if model is Document and object_id == self.document.id:
            return self.document
        if model is IngestionJob and object_id == self.job.id:
            return self.job
        if model is KnowledgeBase and object_id == self.knowledge_base.id:
            return self.knowledge_base
        return None

    def scalars(self, _statement: object) -> FakeScalarResult:
        return FakeScalarResult([])

    def delete(self, obj: object) -> None:
        self.deleted.append(obj)

    def add_all(self, items: list[object]) -> None:
        self.added.extend(items)

    def add(self, item: object) -> None:
        self.added.append(item)

    def flush(self) -> None:
        for item in self.added:
            if hasattr(item, "id") and getattr(item, "id", None) is None:
                setattr(item, "id", uuid.uuid4())

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


class FakeParser:
    def __init__(self, parsed_document: ParsedDocument) -> None:
        self.parsed_document = parsed_document

    def parse(self, file_path, mime_type: str) -> ParsedDocument:  # noqa: ANN001
        return self.parsed_document


class FakeChunkingStrategy(ChunkingStrategy):
    name = "fake"

    def __init__(self, payloads: list[ChunkPayload]) -> None:
        self.payloads = payloads

    def chunk_document(self, pages) -> list[ChunkPayload]:  # noqa: ANN001
        return list(self.payloads)


class FakeEmbeddingService(EmbeddingService):
    model_name = "fake-embedding"
    dimensions = 3

    def embed_text(self, text: str) -> list[float]:
        return [0.1, 0.2, 0.3]

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [[0.1, 0.2, 0.3] for _ in texts]


def build_document_state() -> tuple[SimpleNamespace, SimpleNamespace, SimpleNamespace]:
    knowledge_base = SimpleNamespace(
        id=uuid.uuid4(),
        name="platform-handbook",
        description=None,
        updated_at=utcnow(),
    )
    document = SimpleNamespace(
        id=uuid.uuid4(),
        knowledge_base_id=knowledge_base.id,
        file_name="architecture.md",
        mime_type="text/markdown",
        storage_key="architecture.md",
        checksum="checksum-123",
        status=DocumentStatus.UPLOADED.value,
        extra_meta={"size_bytes": 128},
    )
    job = SimpleNamespace(
        id=uuid.uuid4(),
        document_id=document.id,
        status=JobStatus.QUEUED.value,
        attempts=0,
        error_message=None,
        started_at=None,
        finished_at=None,
    )
    return document, job, knowledge_base


def test_build_cache_key_changes_when_knowledge_base_version_changes() -> None:
    cache_key_a = build_cache_key(
        knowledge_base_id="kb-1",
        knowledge_base_version="2026-04-27T10:00:00+00:00",
        question="How should ingestion work?",
        top_k=5,
        include_debug=False,
    )
    cache_key_b = build_cache_key(
        knowledge_base_id="kb-1",
        knowledge_base_version="2026-04-27T10:05:00+00:00",
        question="How should ingestion work?",
        top_k=5,
        include_debug=False,
    )

    assert cache_key_a != cache_key_b


def test_ingestion_service_enriches_document_metadata_on_success(monkeypatch) -> None:
    monkeypatch.setattr("app.services.ingestion.record_ingestion_job", lambda status: status)

    document, job, knowledge_base = build_document_state()
    session = FakeSession(document=document, job=job, knowledge_base=knowledge_base)
    service = IngestionService(
        embedder=FakeEmbeddingService(),
        chunking_strategy=FakeChunkingStrategy(
            [
                ChunkPayload(
                    chunk_index=0,
                    content="Use worker-backed ingestion to keep uploads responsive.",
                    token_count=8,
                    page_number=1,
                    section_title="Ingestion",
                    metadata={"chunking_strategy": "sliding_window"},
                )
            ]
        ),
    )
    service.parser = FakeParser(
        ParsedDocument(pages=[ParsedPage(page_number=1, text="Use worker-backed ingestion to keep uploads responsive.")])
    )

    service.run(session=session, document_id=document.id, job_id=job.id)

    assert document.status == DocumentStatus.READY.value
    assert job.status == JobStatus.COMPLETED.value
    assert document.extra_meta["chunk_count"] == 1
    assert document.extra_meta["parsed_pages"] == 1
    assert document.extra_meta["embedding_model"] == "fake-embedding"
    assert document.extra_meta["embedding_dimensions"] == 3
    assert document.extra_meta["last_ingestion_error"] is None
    assert session.commits == 2
    assert any(isinstance(item, DocumentChunk) for item in session.added)
    assert any(isinstance(item, ChunkEmbedding) for item in session.added)


def test_ingestion_service_rejects_documents_without_extractable_text(monkeypatch) -> None:
    monkeypatch.setattr("app.services.ingestion.record_ingestion_job", lambda status: status)

    document, job, knowledge_base = build_document_state()
    session = FakeSession(document=document, job=job, knowledge_base=knowledge_base)
    service = IngestionService(
        embedder=FakeEmbeddingService(),
        chunking_strategy=FakeChunkingStrategy([]),
    )
    service.parser = FakeParser(ParsedDocument(pages=[ParsedPage(page_number=1, text="   ")]))

    with pytest.raises(ValidationAppError, match="No extractable text was found"):
        service.run(session=session, document_id=document.id, job_id=job.id)

    assert document.status == DocumentStatus.FAILED.value
    assert job.status == JobStatus.FAILED.value
    assert "No extractable text" in document.extra_meta["last_ingestion_error"]
    assert session.rollbacks == 1
    assert session.commits == 2
