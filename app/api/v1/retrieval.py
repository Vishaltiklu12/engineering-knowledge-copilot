from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_request_id, get_retrieval_service, retrieval_rate_limit
from app.core.config import get_settings
from app.core.exceptions import NotFoundError
from app.models.knowledge_base import KnowledgeBase
from app.schemas.common import MetaBody
from app.schemas.retrieval import RetrievalData, RetrievalRequest, RetrievalResponse, RetrievedChunkData
from app.services.retrieval import RetrievalPipelineService

router = APIRouter(prefix="/retrievals", tags=["retrievals"])


@router.post("/search", response_model=RetrievalResponse, dependencies=[Depends(retrieval_rate_limit)])
def search_retrievals(
    payload: RetrievalRequest,
    db: Session = Depends(get_db),
    request_id: str = Depends(get_request_id),
    retrieval_service: RetrievalPipelineService = Depends(get_retrieval_service),
) -> RetrievalResponse:
    settings = get_settings()
    top_k = payload.top_k or settings.default_top_k

    knowledge_base = db.get(KnowledgeBase, payload.knowledge_base_id)
    if not knowledge_base:
        raise NotFoundError("Knowledge base was not found.")

    retrieval_result = retrieval_service.retrieve(db, payload.knowledge_base_id, payload.question, top_k=top_k)

    chunks = [
        RetrievedChunkData(
            rank=index,
            citation_id=index,
            document_id=hit.document_id,
            document_name=hit.document_name,
            chunk_id=hit.chunk_id,
            chunk_index=hit.chunk_index,
            content=hit.content,
            snippet=hit.content[:240].strip(),
            page=hit.page_number,
            section_title=hit.section_title,
            score=round(hit.score, 4),
            metadata=hit.metadata,
        )
        for index, hit in enumerate(retrieval_result.hits, start=1)
    ]

    return RetrievalResponse(
        data=RetrievalData(
            question=retrieval_result.question,
            top_k=retrieval_result.top_k,
            embedding_model=retrieval_result.embedding_model,
            chunks=chunks,
            citations=retrieval_result.citations,
        ),
        meta=MetaBody(request_id=request_id),
    )
