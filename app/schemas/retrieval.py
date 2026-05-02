import uuid

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import ErrorBody, MetaBody
from app.schemas.query import CitationData


class RetrievalRequest(BaseModel):
    knowledge_base_id: uuid.UUID
    question: str = Field(min_length=3, max_length=2000)
    top_k: int | None = Field(default=None, ge=1, le=50)

    @field_validator("question")
    @classmethod
    def normalize_question(cls, value: str) -> str:
        normalized = " ".join(value.split()).strip()
        if len(normalized) < 3:
            raise ValueError("Question must contain at least 3 non-space characters.")
        return normalized


class RetrievedChunkData(BaseModel):
    rank: int
    citation_id: int
    document_id: uuid.UUID
    document_name: str
    chunk_id: uuid.UUID
    chunk_index: int
    content: str
    snippet: str
    page: int | None = None
    section_title: str | None = None
    score: float
    metadata: dict = Field(default_factory=dict)


class RetrievalData(BaseModel):
    question: str
    top_k: int
    embedding_model: str
    chunks: list[RetrievedChunkData]
    citations: list[CitationData]


class RetrievalResponse(BaseModel):
    data: RetrievalData
    meta: MetaBody
    error: ErrorBody | None = None
