import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.document import Document
from app.schemas.document import DocumentData
from app.services.pagination import PaginationResult, PaginationService


class DocumentCatalogService:
    def __init__(self, pagination_service: PaginationService | None = None) -> None:
        self.pagination_service = pagination_service or PaginationService()

    def list_documents(
        self,
        session: Session,
        *,
        knowledge_base_id: uuid.UUID | None,
        page: int,
        page_size: int,
    ) -> PaginationResult[DocumentData]:
        filters = []
        if knowledge_base_id is not None:
            filters.append(Document.knowledge_base_id == knowledge_base_id)

        total_items = session.execute(select(func.count()).select_from(Document).where(*filters)).scalar_one()
        documents = session.scalars(
            select(Document)
            .where(*filters)
            .order_by(Document.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()

        items = [
            DocumentData(
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
            )
            for document in documents
        ]

        return self.pagination_service.build_result(
            items=items,
            page=page,
            page_size=page_size,
            total_items=total_items,
        )
