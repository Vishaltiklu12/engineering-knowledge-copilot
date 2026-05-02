import uuid

from app.core.config import get_settings
from app.services.metrics import record_ingestion_job
from app.services.retry import RetryPolicy, RetryService
from app.workers.ingestion_tasks import ingest_document_task


class IngestionQueueService:
    def __init__(self, retry_service: RetryService | None = None, task_dispatcher=None) -> None:
        self.settings = get_settings()
        self.retry_service = retry_service or RetryService()
        self.task_dispatcher = task_dispatcher or ingest_document_task

    def enqueue(self, document_id: uuid.UUID, job_id: uuid.UUID) -> None:
        self.retry_service.run(
            lambda: self.task_dispatcher.delay(str(document_id), str(job_id)),
            retryable_exceptions=(Exception,),
            policy=RetryPolicy(
                attempts=self.settings.enqueue_retry_attempts,
                delay_seconds=self.settings.enqueue_retry_delay_seconds,
                backoff_multiplier=self.settings.enqueue_retry_backoff_multiplier,
            ),
            operation_name="ingestion queue dispatch",
        )
        record_ingestion_job("queued")
