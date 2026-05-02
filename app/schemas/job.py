import uuid
from datetime import datetime

from pydantic import BaseModel

from app.schemas.common import ErrorBody, MetaBody


class JobData(BaseModel):
    id: uuid.UUID
    document_id: uuid.UUID
    status: str
    attempts: int
    error_message: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class JobResponse(BaseModel):
    data: JobData
    meta: MetaBody
    error: ErrorBody | None = None
