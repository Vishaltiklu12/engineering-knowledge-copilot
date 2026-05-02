import uuid

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import ErrorBody, MetaBody


class KnowledgeBaseCreateRequest(BaseModel):
    name: str = Field(min_length=3, max_length=80)
    description: str | None = Field(default=None, max_length=500)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = " ".join(value.split()).strip()
        if len(normalized) < 3:
            raise ValueError("Knowledge base name must contain at least 3 non-space characters.")
        return normalized

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class KnowledgeBaseData(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None = None


class KnowledgeBaseResponse(BaseModel):
    data: KnowledgeBaseData
    meta: MetaBody
    error: ErrorBody | None = None


class KnowledgeBaseListData(BaseModel):
    items: list[KnowledgeBaseData]


class KnowledgeBaseListResponse(BaseModel):
    data: KnowledgeBaseListData
    meta: MetaBody
    error: ErrorBody | None = None
