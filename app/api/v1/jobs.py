import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_request_id
from app.core.exceptions import NotFoundError
from app.models.ingestion_job import IngestionJob
from app.schemas.common import MetaBody
from app.schemas.job import JobData, JobResponse

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/{job_id}", response_model=JobResponse)
def get_job(
    job_id: uuid.UUID,
    db: Session = Depends(get_db),
    request_id: str = Depends(get_request_id),
) -> JobResponse:
    job = db.get(IngestionJob, job_id)
    if not job:
        raise NotFoundError("Ingestion job was not found.")

    return JobResponse(
        data=JobData(
            id=job.id,
            document_id=job.document_id,
            status=job.status,
            attempts=job.attempts,
            error_message=job.error_message,
            started_at=job.started_at,
            finished_at=job.finished_at,
            created_at=job.created_at,
            updated_at=job.updated_at,
        ),
        meta=MetaBody(request_id=request_id),
    )
