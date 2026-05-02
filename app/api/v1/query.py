import hashlib
import json
import time
import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import (
    get_db,
    get_pagination_params,
    get_query_history_service,
    get_rag_service,
    get_request_id,
    query_rate_limit,
)
from app.core.config import get_settings
from app.core.exceptions import NotFoundError
from app.models.knowledge_base import KnowledgeBase
from app.schemas.common import MetaBody, PaginationParams
from app.schemas.query import (
    QueryData,
    QueryHistoryListData,
    QueryHistoryListResponse,
    QueryRequest,
    QueryResponse,
)
from app.services.cache import CacheService
from app.services.metrics import record_rag_query
from app.services.query_history import QueryHistoryService
from app.services.rag import RagService

router = APIRouter(prefix="/query", tags=["query"])


def build_cache_key(
    knowledge_base_id: str,
    knowledge_base_version: str,
    question: str,
    top_k: int,
    include_debug: bool,
) -> str:
    fingerprint = hashlib.sha256(
        f"{knowledge_base_id}:{knowledge_base_version}:{top_k}:{include_debug}:{question.strip().lower()}".encode(
            "utf-8"
        )
    ).hexdigest()
    return f"query:{fingerprint}"


@router.get("/history", response_model=QueryHistoryListResponse)
def list_query_history(
    knowledge_base_id: uuid.UUID | None = None,
    pagination: PaginationParams = Depends(get_pagination_params),
    db: Session = Depends(get_db),
    request_id: str = Depends(get_request_id),
    query_history_service: QueryHistoryService = Depends(get_query_history_service),
) -> QueryHistoryListResponse:
    result = query_history_service.list_history(
        session=db,
        knowledge_base_id=knowledge_base_id,
        page=pagination.page,
        page_size=pagination.page_size,
    )
    return QueryHistoryListResponse(
        data=QueryHistoryListData(items=result.items),
        meta=MetaBody(
            request_id=request_id,
            page=result.page,
            page_size=result.page_size,
            total_items=result.total_items,
            total_pages=result.total_pages,
        ),
    )


@router.post("", response_model=QueryResponse, dependencies=[Depends(query_rate_limit)])
def query_knowledge(
    payload: QueryRequest,
    db: Session = Depends(get_db),
    request_id: str = Depends(get_request_id),
    rag_service: RagService = Depends(get_rag_service),
    query_history_service: QueryHistoryService = Depends(get_query_history_service),
) -> QueryResponse:
    settings = get_settings()
    start = time.perf_counter()
    cache = CacheService()
    top_k = payload.top_k or settings.default_top_k

    knowledge_base = db.get(KnowledgeBase, payload.knowledge_base_id)
    if not knowledge_base:
        raise NotFoundError("Knowledge base was not found.")

    cache_key = build_cache_key(
        str(payload.knowledge_base_id),
        knowledge_base.updated_at.isoformat(),
        payload.question,
        top_k,
        payload.include_debug,
    )

    cached = cache.get_json(cache_key)
    cache_hit = cached is not None

    if cached:
        query_data = QueryData.model_validate(
            {
                **cached["data"],
                "query_id": str(uuid.uuid4()),
            }
        )
    else:
        query_data, _ = rag_service.answer(
            db,
            payload.knowledge_base_id,
            payload.question,
            top_k=top_k,
            include_debug=payload.include_debug,
        )

        cache.set_json(
            cache_key,
            {
                "data": json.loads(query_data.model_dump_json()),
            },
        )

    latency_ms = int((time.perf_counter() - start) * 1000)
    query_history_service.record(
        session=db,
        knowledge_base_id=payload.knowledge_base_id,
        question=payload.question,
        cache_hit=cache_hit,
        latency_ms=latency_ms,
        query_data=query_data,
    )
    record_rag_query(answer_status=query_data.answer_status, cache_hit=cache_hit)
    return QueryResponse(
        data=query_data,
        meta=MetaBody(request_id=request_id, latency_ms=latency_ms, cache_hit=cache_hit),
    )
