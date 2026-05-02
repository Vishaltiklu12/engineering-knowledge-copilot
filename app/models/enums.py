from enum import StrEnum


class DocumentStatus(StrEnum):
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class JobStatus(StrEnum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class AnswerStatus(StrEnum):
    GROUNDED = "grounded"
    INSUFFICIENT_CONTEXT = "insufficient_context"
    UNSUPPORTED = "unsupported"
