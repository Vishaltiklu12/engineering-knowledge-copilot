import uuid

from app.services.citations import CitationService
from app.services.embedder import EmbeddingService
from app.services.retrieval import RetrievedChunk, RetrievalPipelineService, VectorSearchRepository


class FakeEmbeddingService(EmbeddingService):
    model_name = "fake-embedding-model"
    dimensions = 3

    def embed_text(self, text: str) -> list[float]:
        assert text == "How do we ingest documents?"
        return [0.1, 0.2, 0.3]


class FakeVectorSearchRepository(VectorSearchRepository):
    def __init__(self) -> None:
        self.calls: list[tuple[object, uuid.UUID, list[float], int]] = []

    def search(
        self,
        session: object,
        knowledge_base_id: uuid.UUID,
        query_embedding: list[float],
        top_k: int,
    ) -> list[RetrievedChunk]:
        self.calls.append((session, knowledge_base_id, query_embedding, top_k))
        return [
            RetrievedChunk(
                document_id=uuid.uuid4(),
                document_name="runbook.md",
                chunk_id=uuid.uuid4(),
                chunk_index=0,
                content="Use a worker queue for background ingestion tasks.",
                page_number=1,
                section_title="Architecture",
                metadata={"chunking_strategy": "sliding_window"},
                score=0.97,
            ),
            RetrievedChunk(
                document_id=uuid.uuid4(),
                document_name="rfc.md",
                chunk_id=uuid.uuid4(),
                chunk_index=1,
                content="Persist embeddings in pgvector to support similarity search.",
                page_number=2,
                section_title="Storage",
                metadata={"chunking_strategy": "sliding_window"},
                score=0.88,
            ),
        ]


def test_retrieval_pipeline_returns_ranked_hits_and_citations() -> None:
    knowledge_base_id = uuid.uuid4()
    session = object()
    repository = FakeVectorSearchRepository()
    pipeline = RetrievalPipelineService(
        embedder=FakeEmbeddingService(),
        vector_repository=repository,
        citation_service=CitationService(),
    )

    result = pipeline.retrieve(
        session=session,
        knowledge_base_id=knowledge_base_id,
        question="How do we ingest documents?",
        top_k=2,
    )

    assert result.embedding_model == "fake-embedding-model"
    assert result.top_k == 2
    assert result.confidence == 0.9542
    assert len(result.hits) == 2
    assert len(result.citations) == 2
    assert result.citations[0].citation_id == 1
    assert result.citations[1].citation_id == 2
    assert repository.calls == [(session, knowledge_base_id, [0.1, 0.2, 0.3], 2)]
