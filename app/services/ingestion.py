import logging
import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import NotFoundError, ValidationAppError
from app.models.chunk import ChunkEmbedding, DocumentChunk
from app.models.document import Document
from app.models.enums import DocumentStatus, JobStatus
from app.models.ingestion_job import IngestionJob
from app.models.knowledge_base import KnowledgeBase
from app.models.mixins import utcnow
from app.services.chunker import ChunkingStrategy, PagePayload, get_chunking_strategy
from app.services.embedder import EmbeddingService, get_embedding_service
from app.services.metrics import record_ingestion_job
from app.services.parser import DocumentParser

logger = logging.getLogger(__name__)


class IngestionService:
    def __init__(
        self,
        embedder: EmbeddingService | None = None,
        chunking_strategy: ChunkingStrategy | None = None,
    ) -> None:
        self.settings = get_settings()
        self.parser = DocumentParser()
        self.chunking_strategy = chunking_strategy or get_chunking_strategy()
        self.embedder = embedder or get_embedding_service()

    def run(self, session: Session, document_id: uuid.UUID, job_id: uuid.UUID) -> None:
        document = session.get(Document, document_id)
        job = session.get(IngestionJob, job_id)

        if not document or not job:
            raise NotFoundError("Document or ingestion job was not found.")

        document.status = DocumentStatus.PROCESSING.value
        job.status = JobStatus.PROCESSING.value
        job.attempts += 1
        job.error_message = None
        job.started_at = utcnow()
        job.finished_at = None
        session.commit()

        try:
            file_path = Path(self.settings.upload_dir) / document.storage_key
            parsed = self.parser.parse(file_path, document.mime_type)

            existing_chunks = session.scalars(
                select(DocumentChunk).where(DocumentChunk.document_id == document.id)
            ).all()
            for chunk in existing_chunks:
                session.delete(chunk)
            session.flush()

            page_payloads = [PagePayload(text=page.text, page_number=page.page_number) for page in parsed.pages]
            chunk_payloads = self.chunking_strategy.chunk_document(page_payloads)
            if not chunk_payloads:
                raise ValidationAppError(
                    "No extractable text was found in the uploaded document.",
                    details={
                        "document_id": str(document.id),
                        "file_name": document.file_name,
                        "mime_type": document.mime_type,
                    },
                )

            chunk_models: list[DocumentChunk] = []
            for payload in chunk_payloads:
                chunk_models.append(
                    DocumentChunk(
                        document_id=document.id,
                        chunk_index=payload.chunk_index,
                        content=payload.content,
                        token_count=payload.token_count,
                        section_title=payload.section_title,
                        page_number=payload.page_number,
                        extra_meta=payload.metadata,
                    )
                )

            session.add_all(chunk_models)
            session.flush()

            embeddings = self.embedder.embed_texts([chunk.content for chunk in chunk_models])
            for chunk, vector in zip(chunk_models, embeddings, strict=True):
                session.add(
                    ChunkEmbedding(
                        chunk_id=chunk.id,
                        model_name=self.embedder.model_name,
                        dimensions=self.embedder.dimensions,
                        embedding=vector,
                    )
                )

            document.status = DocumentStatus.READY.value
            document.extra_meta = {
                **(document.extra_meta or {}),
                "parsed_pages": len(parsed.pages),
                "chunk_count": len(chunk_models),
                "embedding_model": self.embedder.model_name,
                "embedding_dimensions": self.embedder.dimensions,
                "last_ingestion_error": None,
            }
            job.status = JobStatus.COMPLETED.value
            job.finished_at = utcnow()
            self._touch_knowledge_base(session, document.knowledge_base_id)
            session.commit()
            record_ingestion_job(JobStatus.COMPLETED.value)
            logger.info("Completed ingestion for document %s", document.id)
        except Exception as exc:
            session.rollback()
            document = session.get(Document, document_id)
            job = session.get(IngestionJob, job_id)
            if document:
                document.status = DocumentStatus.FAILED.value
                document.extra_meta = {
                    **(document.extra_meta or {}),
                    "last_ingestion_error": str(exc),
                }
                self._touch_knowledge_base(session, document.knowledge_base_id)
            if job:
                job.status = JobStatus.FAILED.value
                job.error_message = str(exc)
                job.finished_at = utcnow()
            session.commit()
            record_ingestion_job(JobStatus.FAILED.value)
            logger.exception("Ingestion failed for document %s", document_id)
            raise

    @staticmethod
    def _touch_knowledge_base(session: Session, knowledge_base_id: uuid.UUID) -> None:
        knowledge_base = session.get(KnowledgeBase, knowledge_base_id)
        if knowledge_base:
            knowledge_base.updated_at = utcnow()
