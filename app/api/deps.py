from functools import lru_cache

from fastapi import Depends, Query, Request
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import ValidationAppError
from app.db.session import get_db_session
from app.schemas.common import PaginationParams
from app.services.contact import ContactService
from app.services.document_catalog import DocumentCatalogService
from app.services.ingestion_queue import IngestionQueueService
from app.services.query_history import QueryHistoryService
from app.services.rag import RagService
from app.services.rate_limit import RateLimiterService
from app.services.retrieval import RetrievalPipelineService


def get_db(session: Session = Depends(get_db_session)) -> Session:
    return session


def get_request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "req_unknown")


def get_rag_service() -> RagService:
    return RagService()


def get_retrieval_service() -> RetrievalPipelineService:
    return RetrievalPipelineService()


def get_query_history_service() -> QueryHistoryService:
    return QueryHistoryService()


def get_document_catalog_service() -> DocumentCatalogService:
    return DocumentCatalogService()


def get_ingestion_queue_service() -> IngestionQueueService:
    return IngestionQueueService()


def get_contact_service() -> ContactService:
    return ContactService()


@lru_cache
def get_rate_limiter_service() -> RateLimiterService:
    return RateLimiterService()


def get_pagination_params(
    page: int = Query(default=1, ge=1),
    page_size: int | None = Query(default=None, ge=1),
) -> PaginationParams:
    settings = get_settings()
    resolved_page_size = page_size or settings.default_page_size
    if resolved_page_size > settings.max_page_size:
        raise ValidationAppError(
            "Requested page size exceeds the configured maximum.",
            details={
                "page_size": resolved_page_size,
                "max_page_size": settings.max_page_size,
            },
        )
    return PaginationParams(page=page, page_size=resolved_page_size)


def make_rate_limit_dependency(scope: str, limit_setting_name: str, window_seconds: int = 60):
    def dependency(
        request: Request,
        rate_limiter: RateLimiterService = Depends(get_rate_limiter_service),
    ) -> None:
        settings = get_settings()
        rate_limiter.enforce_request_limit(
            request,
            scope=scope,
            limit=getattr(settings, limit_setting_name),
            window_seconds=window_seconds,
        )

    return dependency


upload_rate_limit = make_rate_limit_dependency("document_upload", "upload_rate_limit_per_minute")
query_rate_limit = make_rate_limit_dependency("query", "query_rate_limit_per_minute")
retrieval_rate_limit = make_rate_limit_dependency("retrieval", "retrieval_rate_limit_per_minute")
contact_rate_limit = make_rate_limit_dependency("contact", "contact_rate_limit_per_minute")
