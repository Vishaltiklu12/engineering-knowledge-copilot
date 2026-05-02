import uuid

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import (
    get_db,
    get_document_catalog_service,
    get_ingestion_queue_service,
    get_pagination_params,
    get_request_id,
    upload_rate_limit,
)
from app.core.exceptions import ConflictError, ExternalDependencyError, NotFoundError
from app.models.document import Document
from app.models.enums import DocumentStatus, JobStatus
from app.models.ingestion_job import IngestionJob
from app.models.knowledge_base import KnowledgeBase
from app.models.mixins import utcnow
from app.schemas.common import MetaBody, PaginationParams
from app.schemas.document import (
    DocumentData,
    DocumentListData,
    DocumentListResponse,
    DocumentResponse,
    DocumentUploadData,
    DocumentUploadResponse,
)
from app.services.document_catalog import DocumentCatalogService
from app.services.ingestion_queue import IngestionQueueService
from app.services.storage import LocalStorageService
from app.services.validation import DocumentUploadValidator

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("", response_model=DocumentListResponse)
def list_documents(
    knowledge_base_id: uuid.UUID | None = Query(default=None),
    pagination: PaginationParams = Depends(get_pagination_params),
    db: Session = Depends(get_db),
    request_id: str = Depends(get_request_id),
    document_catalog_service: DocumentCatalogService = Depends(get_document_catalog_service),
) -> DocumentListResponse:
    result = document_catalog_service.list_documents(
        session=db,
        knowledge_base_id=knowledge_base_id,
        page=pagination.page,
        page_size=pagination.page_size,
    )
    return DocumentListResponse(
        data=DocumentListData(items=result.items),
        meta=MetaBody(
            request_id=request_id,
            page=result.page,
            page_size=result.page_size,
            total_items=result.total_items,
            total_pages=result.total_pages,
        ),
    )


@router.post(
    "/upload",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(upload_rate_limit)],
)
def upload_document(
    knowledge_base_id: uuid.UUID = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    request_id: str = Depends(get_request_id),
    ingestion_queue_service: IngestionQueueService = Depends(get_ingestion_queue_service),
) -> DocumentUploadResponse:
    knowledge_base = db.get(KnowledgeBase, knowledge_base_id)
    if not knowledge_base:
        raise NotFoundError("Knowledge base was not found.")

    DocumentUploadValidator().validate(file)
    storage = LocalStorageService()
    stored = storage.save_upload(file)

    duplicate_document = db.scalar(
        select(Document)
        .where(Document.knowledge_base_id == knowledge_base.id)
        .where(Document.checksum == stored.checksum)
        .where(
            Document.status.in_(
                [
                    DocumentStatus.UPLOADED.value,
                    DocumentStatus.PROCESSING.value,
                    DocumentStatus.READY.value,
                ]
            )
        )
    )
    if duplicate_document:
        storage.delete_upload(stored.storage_key)
        raise ConflictError(
            "A document with the same contents already exists in this knowledge base.",
            details={
                "existing_document_id": str(duplicate_document.id),
                "existing_status": duplicate_document.status,
                "knowledge_base_id": str(knowledge_base.id),
            },
        )

    document = Document(
        knowledge_base_id=knowledge_base.id,
        file_name=file.filename or stored.storage_key,
        mime_type=file.content_type or "application/octet-stream",
        storage_key=stored.storage_key,
        checksum=stored.checksum,
        status=DocumentStatus.UPLOADED.value,
        extra_meta={"size_bytes": stored.size_bytes},
    )
    job = IngestionJob(document=document)

    knowledge_base.updated_at = utcnow()
    db.add_all([document, job])
    db.commit()
    db.refresh(document)
    db.refresh(job)

    try:
        ingestion_queue_service.enqueue(document.id, job.id)
    except Exception as exc:
        document.status = DocumentStatus.FAILED.value
        job.status = JobStatus.FAILED.value
        job.error_message = f"Failed to enqueue ingestion task: {type(exc).__name__}"
        db.commit()
        raise ExternalDependencyError(
            "Document was stored, but the ingestion task could not be enqueued.",
            details={"broker": "celery/redis"},
        ) from exc

    return DocumentUploadResponse(
        data=DocumentUploadData(document_id=document.id, job_id=job.id, status=job.status),
        meta=MetaBody(request_id=request_id),
    )


@router.get("/{document_id}", response_model=DocumentResponse)
def get_document(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    request_id: str = Depends(get_request_id),
) -> DocumentResponse:
    document = db.get(Document, document_id)
    if not document:
        raise NotFoundError("Document was not found.")

    return DocumentResponse(
        data=DocumentData(
            id=document.id,
            knowledge_base_id=document.knowledge_base_id,
            file_name=document.file_name,
            mime_type=document.mime_type,
            storage_key=document.storage_key,
            checksum=document.checksum,
            status=document.status,
            metadata=document.extra_meta,
            created_at=document.created_at,
            updated_at=document.updated_at,
        ),
        meta=MetaBody(request_id=request_id),
    )
