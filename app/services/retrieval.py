import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.models.chunk import ChunkEmbedding, DocumentChunk
from app.models.document import Document
from app.models.enums import DocumentStatus
from app.schemas.query import CitationData
from app.services.citations import CitationService
from app.services.embedder import EmbeddingService, get_embedding_service


@dataclass
class RetrievedChunk:
    document_id: uuid.UUID
    document_name: str
    chunk_id: uuid.UUID
    chunk_index: int
    content: str
    page_number: int | None
    section_title: str | None
    metadata: dict
    score: float


@dataclass
class RetrievalResult:
    question: str
    top_k: int
    embedding_model: str
    confidence: float
    hits: list[RetrievedChunk]
    citations: list[CitationData]


class VectorSearchRepository(ABC):
    @abstractmethod
    def search(
        self,
        session: Session,
        knowledge_base_id: uuid.UUID,
        query_embedding: list[float],
        top_k: int,
    ) -> list[RetrievedChunk]:
        raise NotImplementedError


class PgVectorSearchRepository(VectorSearchRepository):
    def build_query(self, knowledge_base_id: uuid.UUID, query_embedding: list[float], top_k: int) -> Select:
        distance = ChunkEmbedding.embedding.cosine_distance(query_embedding).label("distance")
        return (
            select(DocumentChunk, Document, distance)
            .join(ChunkEmbedding, ChunkEmbedding.chunk_id == DocumentChunk.id)
            .join(Document, Document.id == DocumentChunk.document_id)
            .where(Document.knowledge_base_id == knowledge_base_id)
            .where(Document.status == DocumentStatus.READY.value)
            .order_by(distance.asc())
            .limit(top_k)
        )

    def search(
        self,
        session: Session,
        knowledge_base_id: uuid.UUID,
        query_embedding: list[float],
        top_k: int,
    ) -> list[RetrievedChunk]:
        rows = session.execute(self.build_query(knowledge_base_id, query_embedding, top_k)).all()

        results: list[RetrievedChunk] = []
        for chunk, document, distance in rows:
            score = max(0.0, min(1.0, 1.0 - float(distance)))
            results.append(
                RetrievedChunk(
                    document_id=document.id,
                    document_name=document.file_name,
                    chunk_id=chunk.id,
                    chunk_index=chunk.chunk_index,
                    content=chunk.content,
                    page_number=chunk.page_number,
                    section_title=chunk.section_title,
                    metadata=chunk.extra_meta,
                    score=score,
                )
            )
        return results


class RetrievalPipelineService:
    def __init__(
        self,
        embedder: EmbeddingService | None = None,
        vector_repository: VectorSearchRepository | None = None,
        citation_service: CitationService | None = None,
    ) -> None:
        self.embedder = embedder or get_embedding_service()
        self.vector_repository = vector_repository or PgVectorSearchRepository()
        self.citation_service = citation_service or CitationService()

    def retrieve(
        self,
        session: Session,
        knowledge_base_id: uuid.UUID,
        question: str,
        top_k: int,
    ) -> RetrievalResult:
        query_embedding = self.embedder.embed_text(question)
        hits = self.vector_repository.search(session, knowledge_base_id, query_embedding, top_k)
        citations = self.citation_service.build(hits)
        return RetrievalResult(
            question=question,
            top_k=top_k,
            embedding_model=self.embedder.model_name,
            confidence=self.calculate_confidence(hits),
            hits=hits,
            citations=citations,
        )

    @staticmethod
    def calculate_confidence(hits: list[RetrievedChunk]) -> float:
        if not hits:
            return 0.0

        considered_scores = [hit.score for hit in hits[: min(3, len(hits))]]
        top_score = considered_scores[0]
        mean_score = sum(considered_scores) / len(considered_scores)
        confidence = (0.65 * top_score) + (0.35 * mean_score)
        return round(max(0.0, min(1.0, confidence)), 4)
