import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import ErrorBody, MetaBody


class QueryRequest(BaseModel):
    knowledge_base_id: uuid.UUID
    question: str = Field(min_length=3, max_length=2000)
    top_k: int | None = Field(default=None, ge=1, le=20)
    include_debug: bool = False

    @field_validator("question")
    @classmethod
    def normalize_question(cls, value: str) -> str:
        normalized = " ".join(value.split()).strip()
        if len(normalized) < 3:
            raise ValueError("Question must contain at least 3 non-space characters.")
        return normalized


class CitationData(BaseModel):
    citation_id: int
    document_id: uuid.UUID
    document_name: str
    chunk_id: uuid.UUID
    snippet: str
    page: int | None = None
    score: float


class QueryData(BaseModel):
    query_id: uuid.UUID
    answer_status: str
    answer: str | None = None
    citations: list[CitationData]
    confidence: float = Field(ge=0.0, le=1.0)
    follow_up_questions: list[str] = Field(default_factory=list)
    rejection_reason: str | None = None
    debug: dict[str, Any] | None = None


class QueryResponse(BaseModel):
    data: QueryData
    meta: MetaBody
    error: ErrorBody | None = None


class QueryHistoryItemData(BaseModel):
    id: uuid.UUID
    knowledge_base_id: uuid.UUID
    question: str
    answer_status: str
    answer_preview: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    citations_count: int = Field(ge=0)
    cache_hit: bool
    latency_ms: int = Field(ge=0)
    created_at: datetime


class QueryHistoryListData(BaseModel):
    items: list[QueryHistoryItemData]


class QueryHistoryListResponse(BaseModel):
    data: QueryHistoryListData
    meta: MetaBody
    error: ErrorBody | None = None
