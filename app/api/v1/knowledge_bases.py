from fastapi import APIRouter, Depends, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_pagination_params, get_request_id
from app.schemas.common import MetaBody, PaginationParams
from app.schemas.knowledge_base import (
    KnowledgeBaseCreateRequest,
    KnowledgeBaseData,
    KnowledgeBaseListData,
    KnowledgeBaseListResponse,
    KnowledgeBaseResponse,
)
from app.models.knowledge_base import KnowledgeBase

router = APIRouter(prefix="/knowledge-bases", tags=["knowledge-bases"])


@router.get("", response_model=KnowledgeBaseListResponse)
def list_knowledge_bases(
    pagination: PaginationParams = Depends(get_pagination_params),
    db: Session = Depends(get_db),
    request_id: str = Depends(get_request_id),
) -> KnowledgeBaseListResponse:
    total_items = db.execute(select(func.count()).select_from(KnowledgeBase)).scalar_one()
    knowledge_bases = db.scalars(
        select(KnowledgeBase)
        .order_by(KnowledgeBase.created_at.desc())
        .offset((pagination.page - 1) * pagination.page_size)
        .limit(pagination.page_size)
    ).all()

    return KnowledgeBaseListResponse(
        data=KnowledgeBaseListData(
            items=[
                KnowledgeBaseData(
                    id=knowledge_base.id,
                    name=knowledge_base.name,
                    description=knowledge_base.description,
                )
                for knowledge_base in knowledge_bases
            ]
        ),
        meta=MetaBody(
            request_id=request_id,
            page=pagination.page,
            page_size=pagination.page_size,
            total_items=total_items,
            total_pages=(total_items + pagination.page_size - 1) // pagination.page_size if total_items else 0,
        ),
    )


@router.post("", response_model=KnowledgeBaseResponse, status_code=status.HTTP_201_CREATED)
def create_knowledge_base(
    payload: KnowledgeBaseCreateRequest,
    db: Session = Depends(get_db),
    request_id: str = Depends(get_request_id),
) -> KnowledgeBaseResponse:
    knowledge_base = KnowledgeBase(name=payload.name, description=payload.description)
    db.add(knowledge_base)
    db.commit()
    db.refresh(knowledge_base)
    return KnowledgeBaseResponse(
        data=KnowledgeBaseData(
            id=knowledge_base.id,
            name=knowledge_base.name,
            description=knowledge_base.description,
        ),
        meta=MetaBody(request_id=request_id),
    )
