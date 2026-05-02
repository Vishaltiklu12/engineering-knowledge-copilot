import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ErrorBody, MetaBody


class DocumentUploadData(BaseModel):
    document_id: uuid.UUID
    job_id: uuid.UUID
    status: str


class DocumentUploadResponse(BaseModel):
    data: DocumentUploadData
    meta: MetaBody
    error: ErrorBody | None = None


class DocumentData(BaseModel):
    id: uuid.UUID
    knowledge_base_id: uuid.UUID
    file_name: str
    mime_type: str
    storage_key: str
    checksum: str
    status: str
    metadata: dict = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class DocumentResponse(BaseModel):
    data: DocumentData
    meta: MetaBody
    error: ErrorBody | None = None


class DocumentListData(BaseModel):
    items: list[DocumentData]


class DocumentListResponse(BaseModel):
    data: DocumentListData
    meta: MetaBody
    error: ErrorBody | None = None
