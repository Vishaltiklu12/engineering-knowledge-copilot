import uuid

from app.services.ingestion_queue import IngestionQueueService
from app.services.retry import RetryService


class FlakyDispatcher:
    def __init__(self) -> None:
        self.calls = 0
        self.enqueued: list[tuple[str, str]] = []

    def delay(self, document_id: str, job_id: str) -> None:
        self.calls += 1
        if self.calls < 3:
            raise RuntimeError("broker unavailable")
        self.enqueued.append((document_id, job_id))


def test_ingestion_queue_service_retries_before_success() -> None:
    dispatcher = FlakyDispatcher()
    service = IngestionQueueService(
        retry_service=RetryService(sleeper=lambda _: None),
        task_dispatcher=dispatcher,
    )
    document_id = uuid.uuid4()
    job_id = uuid.uuid4()

    service.enqueue(document_id, job_id)

    assert dispatcher.calls == 3
    assert dispatcher.enqueued == [(str(document_id), str(job_id))]
