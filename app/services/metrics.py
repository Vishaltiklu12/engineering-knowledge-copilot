from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

http_requests_total = Counter(
    "engineering_knowledge_http_requests_total",
    "Total HTTP requests handled by the API.",
    ("method", "path", "status_code"),
)
http_request_duration_seconds = Histogram(
    "engineering_knowledge_http_request_duration_seconds",
    "Latency distribution for HTTP requests.",
    ("method", "path"),
)
rag_queries_total = Counter(
    "engineering_knowledge_rag_queries_total",
    "Total RAG query requests processed.",
    ("answer_status", "cache_hit"),
)
ingestion_jobs_total = Counter(
    "engineering_knowledge_ingestion_jobs_total",
    "Total ingestion job transitions recorded.",
    ("status",),
)
rate_limit_exceeded_total = Counter(
    "engineering_knowledge_rate_limit_exceeded_total",
    "Total rate-limit rejections.",
    ("scope",),
)


def observe_http_request(method: str, path: str, status_code: int, duration_seconds: float) -> None:
    http_requests_total.labels(method=method, path=path, status_code=str(status_code)).inc()
    http_request_duration_seconds.labels(method=method, path=path).observe(duration_seconds)


def record_rag_query(answer_status: str, cache_hit: bool) -> None:
    rag_queries_total.labels(answer_status=answer_status, cache_hit=str(cache_hit).lower()).inc()


def record_ingestion_job(status: str) -> None:
    ingestion_jobs_total.labels(status=status).inc()


def record_rate_limit_exceeded(scope: str) -> None:
    rate_limit_exceeded_total.labels(scope=scope).inc()


def render_metrics() -> bytes:
    return generate_latest()


__all__ = [
    "CONTENT_TYPE_LATEST",
    "observe_http_request",
    "record_rag_query",
    "record_ingestion_job",
    "record_rate_limit_exceeded",
    "render_metrics",
]
