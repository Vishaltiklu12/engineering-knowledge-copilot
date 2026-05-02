import uuid

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.services.ingestion import IngestionService
from app.workers.celery_app import celery_app

settings = get_settings()


@celery_app.task(
    name="app.workers.ingestion_tasks.ingest_document_task",
    autoretry_for=(Exception,),
    acks_late=True,
    retry_backoff=settings.ingestion_task_retry_backoff_seconds,
    retry_jitter=True,
    retry_kwargs={"max_retries": settings.ingestion_task_max_retries},
)
def ingest_document_task(document_id: str, job_id: str) -> None:
    service = IngestionService()
    with SessionLocal() as session:
        service.run(session, uuid.UUID(document_id), uuid.UUID(job_id))
