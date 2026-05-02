from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "engineering-knowledge-copilot"
    environment: str = "local"
    log_level: str = "INFO"
    api_v1_prefix: str = "/v1"
    auto_create_schema: bool = True
    require_database_on_startup: bool = False
    cors_allow_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/knowledge_copilot"
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    upload_dir: Path = Path("./data/uploads")
    max_upload_size_mb: int = 25
    allowed_upload_extensions: str = ".txt,.md,.pdf,.docx"
    allowed_upload_mime_types: str = (
        "text/plain,text/markdown,application/pdf,"
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    chunking_strategy: str = "sliding_window"
    chunk_size_words: int = 220
    chunk_overlap_words: int = 40

    embedding_provider: str = "placeholder"
    embedding_dimensions: int = 256
    embedding_model: str = "local-deterministic-v1"

    llm_provider: str = "placeholder"
    llm_model: str = "extractive-rag-v1"
    llm_temperature: float = Field(default=0.1, ge=0.0, le=1.0)
    llm_max_output_tokens: int = Field(default=500, ge=64, le=4096)
    grounded_answer_min_confidence: float = Field(default=0.45, ge=0.0, le=1.0)

    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_organization: str = ""
    openai_project: str = ""
    model_request_timeout_seconds: int = Field(default=45, ge=5, le=300)
    model_retry_attempts: int = Field(default=3, ge=1, le=10)
    model_retry_delay_seconds: float = Field(default=0.5, ge=0.0, le=30.0)
    model_retry_backoff_multiplier: float = Field(default=2.0, ge=1.0, le=10.0)

    query_cache_ttl_seconds: int = 300
    default_top_k: int = Field(default=5, ge=1, le=20)
    default_page_size: int = Field(default=20, ge=1, le=100)
    max_page_size: int = Field(default=100, ge=1, le=200)

    upload_rate_limit_per_minute: int = Field(default=10, ge=1)
    query_rate_limit_per_minute: int = Field(default=60, ge=1)
    retrieval_rate_limit_per_minute: int = Field(default=90, ge=1)
    contact_rate_limit_per_minute: int = Field(default=12, ge=1)

    enqueue_retry_attempts: int = Field(default=3, ge=1, le=10)
    enqueue_retry_delay_seconds: float = Field(default=0.25, ge=0.0, le=30.0)
    enqueue_retry_backoff_multiplier: float = Field(default=2.0, ge=1.0, le=10.0)
    ingestion_task_max_retries: int = Field(default=5, ge=0, le=20)
    ingestion_task_retry_backoff_seconds: int = Field(default=5, ge=1, le=300)

    contact_owner_name: str = "Yasaswini Adivanne"
    contact_receiver_email: str = "adivanne.yasaswini@gmail.com"
    smtp_host: str = ""
    smtp_port: int = Field(default=587, ge=1, le=65535)
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from_email: str = ""
    smtp_from_name: str = "Yasaswini Portfolio"
    smtp_use_starttls: bool = True
    smtp_use_ssl: bool = False
    smtp_timeout_seconds: int = Field(default=20, ge=1, le=120)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    return settings


def get_cors_origins(settings: Settings) -> list[str]:
    return [origin.strip() for origin in settings.cors_allow_origins.split(",") if origin.strip()]


def get_allowed_upload_extensions(settings: Settings) -> set[str]:
    return {extension.strip().lower() for extension in settings.allowed_upload_extensions.split(",") if extension.strip()}


def get_allowed_upload_mime_types(settings: Settings) -> set[str]:
    return {mime_type.strip().lower() for mime_type in settings.allowed_upload_mime_types.split(",") if mime_type.strip()}
