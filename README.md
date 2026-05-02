# Engineering Knowledge Copilot Backend

Backend-first reference architecture for a portfolio-grade Engineering Knowledge Copilot. The project is structured as a modular monolith with a separate worker so it stays easy to reason about locally while still demonstrating production-minded boundaries.

## Architecture Overview

### Core components
- `FastAPI` API service for uploads, query, job status, and health checks.
- `Celery` worker for ingestion, chunking, embedding, and retryable background work.
- `PostgreSQL + pgvector` for document metadata, chunks, vector search, and query logs.
- `Redis` for Celery broker/result backend plus hot query caching.
- Prometheus-style `/metrics` endpoint for request, ingestion, query, and rate-limit metrics.
- Local filesystem storage for uploaded files during development, abstracted behind `StorageService` so it can be replaced with S3 or GCS later.
- `EmbeddingService` and `LLMService` abstractions so placeholder model adapters can be swapped for real providers later.

### Request and ingestion flow
1. Client uploads a document to `POST /v1/documents/upload`.
2. API validates the file extension, content type, and payload size before persisting the upload.
3. API stores the raw file, rejects duplicate checksums within the same knowledge base, creates `documents` and `ingestion_jobs` rows, and enqueues a Celery task with bounded enqueue retries.
4. Worker parses the file, rejects uploads with no extractable text, chunks the text, creates embeddings, and stores chunks plus vectors in Postgres.
5. Celery retries transient worker failures with exponential backoff.
6. Document status flips from `uploaded` to `ready` once retrieval data is available.

### Query and RAG flow
1. Client calls `POST /v1/query` with `knowledge_base_id` and a question.
2. API checks Redis for a cached response.
3. Cache keys are versioned by the knowledge base freshness timestamp so new uploads invalidate stale answers automatically.
4. Retrieval service embeds the query and searches `document_chunks` through `chunk_embeddings` using pgvector similarity.
5. RAG service produces a grounded answer from retrieved chunks.
6. Citation service attaches chunk-level citations and snippets.
7. API logs the query, stores citation links, caches the response, and returns a structured JSON envelope.

### Retrieval pipeline
- `SlidingWindowChunkingStrategy` splits parsed text into overlapping chunks with source metadata.
- `EmbeddingService` abstracts query and chunk embedding generation.
- `PgVectorSearchRepository` performs cosine similarity search with pgvector.
- `RetrievalPipelineService` orchestrates embedding, top-k search, and citation mapping.
- `POST /v1/retrievals/search` exposes raw retrieval hits for debugging and evaluation.

### Grounding strategy
- Answers are citation-backed at the chunk level.
- If retrieval quality is weak, the API rejects unsupported answers instead of fabricating them.
- The local scaffold uses a deterministic placeholder embedder and a placeholder extractive LLM adapter so the pipeline works offline.
- The backend now also supports an OpenAI-compatible provider path for both embeddings and grounded answer generation. In production, point `OPENAI_BASE_URL` at the provider you want to use and set `OPENAI_API_KEY`, `EMBEDDING_PROVIDER`, and `LLM_PROVIDER` accordingly.

### Production-minded concerns
- `pydantic-settings` for config management.
- JSON logging with request IDs and worker correlation.
- Centralized exception handling with stable error codes.
- Request validation for JSON payloads, multipart uploads, and pagination parameters.
- Duplicate upload protection via checksum checks scoped to a knowledge base.
- Redis-backed rate limiting with in-memory fallback for local development.
- Retry policies for queue dispatch and background ingestion work.
- Automatic query-cache freshness on document lifecycle updates.
- Paginated list endpoints for knowledge bases, documents, and query history.
- Prometheus counters and latency histograms exposed at `/metrics`.
- Clear separation between API, services, models, schemas, and worker logic.
- Docker Compose for local development with Postgres, Redis, API, and worker processes.

## Folder Structure

```text
backend/
  app/
    api/
      v1/
        documents.py
        health.py
        jobs.py
        knowledge_bases.py
        query.py
        retrieval.py
      deps.py
      errors.py
    core/
      config.py
      exceptions.py
      logging.py
    db/
      base.py
      migrations/
      session.py
    models/
      chunk.py
      document.py
      enums.py
      ingestion_job.py
      knowledge_base.py
      mixins.py
      query_log.py
    schemas/
      common.py
      document.py
      job.py
      knowledge_base.py
      query.py
      retrieval.py
    services/
      cache.py
      chunker.py
      citations.py
      document_catalog.py
      embedder.py
      ingestion.py
      ingestion_queue.py
      llm.py
      metrics.py
      pagination.py
      parser.py
      query_history.py
      rag.py
      rate_limit.py
      retrieval.py
      retry.py
      storage.py
      validation.py
    workers/
      celery_app.py
      ingestion_tasks.py
    main.py
  data/
    uploads/
  docker/
    postgres/
      init.sql
    worker.Dockerfile
  tests/
    unit/
    integration/
    e2e/
  Dockerfile
  docker-compose.yml
  pyproject.toml
  .env.example
  README.md
```

## API Design

### `POST /v1/knowledge-bases`
Create a logical container for a set of documents.

Request:
```json
{
  "name": "platform-handbook",
  "description": "Architecture notes, RFCs, and runbooks"
}
```

Response:
```json
{
  "data": {
    "id": "b1f10aa3-4252-4d63-8d6d-cda25c248d9d",
    "name": "platform-handbook",
    "description": "Architecture notes, RFCs, and runbooks"
  },
  "meta": {
    "request_id": "req_123"
  },
  "error": null
}
```

### `GET /v1/knowledge-bases`
Returns paginated knowledge bases.

Query params:
- `page` default `1`
- `page_size` default `20`

### `GET /v1/documents`
Returns paginated document metadata, optionally filtered by `knowledge_base_id`.

Query params:
- `knowledge_base_id` optional UUID filter
- `page` default `1`
- `page_size` default `20`

### `POST /v1/documents/upload`
Accepts multipart file upload plus a `knowledge_base_id`. Uploads are validated, rate limited, stored immediately, and queued for worker ingestion.

### `GET /v1/documents/{document_id}`
Returns document metadata, checksum, storage key, and ingestion status.

### `GET /v1/jobs/{job_id}`
Returns ingestion job state, attempts, timestamps, and failure details if any.

### `POST /v1/query`
Runs retrieval-augmented generation and returns a grounded answer.

Request:
```json
{
  "knowledge_base_id": "b1f10aa3-4252-4d63-8d6d-cda25c248d9d",
  "question": "How should we structure async ingestion for document uploads?",
  "top_k": 5,
  "include_debug": false
}
```

Response:
```json
{
  "data": {
    "query_id": "f8a5d89d-4b53-4c26-a69f-dd0e0cdca5fe",
    "answer_status": "grounded",
    "answer": "Use an API + worker split so uploads stay fast while ingestion runs asynchronously. The retrieved documents point to background workers for parsing, chunking, and vector indexing [1] [2].",
    "citations": [
      {
        "citation_id": 1,
        "document_id": "dc8d998b-a9db-4478-8b1c-d6f15d2888af",
        "document_name": "architecture.md",
        "chunk_id": "798274ab-0a34-4218-bd17-e1e56b8bd14c",
        "snippet": "Asynchronous ingestion prevents user-facing upload latency from ballooning.",
        "page": 1,
        "score": 0.91
      }
    ],
    "confidence": 0.91,
    "follow_up_questions": [
      "Do you want a deeper breakdown of the guidance in architecture.md?",
      "Should I compare the cited chunks and highlight tradeoffs or inconsistencies?"
    ],
    "rejection_reason": null
  },
  "meta": {
    "request_id": "req_123",
    "latency_ms": 142,
    "cache_hit": false
  },
  "error": null
}
```

Low-confidence response:
```json
{
  "data": {
    "query_id": "0ca884f1-b7d0-4bc7-bf87-3c8b18f55e16",
    "answer_status": "unsupported",
    "answer": null,
    "citations": [
      {
        "citation_id": 1,
        "document_id": "dc8d998b-a9db-4478-8b1c-d6f15d2888af",
        "document_name": "architecture.md",
        "chunk_id": "798274ab-0a34-4218-bd17-e1e56b8bd14c",
        "snippet": "Asynchronous ingestion prevents user-facing upload latency from ballooning.",
        "page": 1,
        "score": 0.18
      }
    ],
    "confidence": 0.18,
    "follow_up_questions": [
      "Should I show the top retrieved chunks from architecture.md instead of answering directly?",
      "Would you like me to narrow the question to a subsystem, API, or service boundary?",
      "Should I compare only the highest-scoring cited chunks for stronger grounding?"
    ],
    "rejection_reason": "Retrieved evidence did not meet the minimum confidence threshold for a grounded answer."
  },
  "meta": {
    "request_id": "req_124",
    "latency_ms": 57,
    "cache_hit": false
  },
  "error": null
}
```

### `GET /v1/query/history`
Returns paginated query history and structured output summaries, optionally filtered by `knowledge_base_id`.

Each item includes:
- question text
- answer status
- answer preview
- confidence
- citation count
- cache hit flag
- latency
- creation timestamp

### `POST /v1/retrievals/search`
Runs top-k similarity retrieval and returns raw chunk hits plus citation metadata that maps each chunk back to its source document.

Request:
```json
{
  "knowledge_base_id": "b1f10aa3-4252-4d63-8d6d-cda25c248d9d",
  "question": "How should we structure async ingestion for document uploads?",
  "top_k": 3
}
```

Response:
```json
{
  "data": {
    "question": "How should we structure async ingestion for document uploads?",
    "top_k": 3,
    "embedding_model": "local-deterministic-v1",
    "chunks": [
      {
        "rank": 1,
        "citation_id": 1,
        "document_id": "dc8d998b-a9db-4478-8b1c-d6f15d2888af",
        "document_name": "architecture.md",
        "chunk_id": "798274ab-0a34-4218-bd17-e1e56b8bd14c",
        "chunk_index": 12,
        "content": "Asynchronous ingestion prevents user-facing upload latency from ballooning.",
        "snippet": "Asynchronous ingestion prevents user-facing upload latency from ballooning.",
        "page": 1,
        "section_title": "Ingestion",
        "score": 0.91,
        "metadata": {
          "chunking_strategy": "sliding_window"
        }
      }
    ],
    "citations": [
      {
        "citation_id": 1,
        "document_id": "dc8d998b-a9db-4478-8b1c-d6f15d2888af",
        "document_name": "architecture.md",
        "chunk_id": "798274ab-0a34-4218-bd17-e1e56b8bd14c",
        "snippet": "Asynchronous ingestion prevents user-facing upload latency from ballooning.",
        "page": 1,
        "score": 0.91
      }
    ]
  },
  "meta": {
    "request_id": "req_123"
  },
  "error": null
}
```

### `GET /metrics`
Returns Prometheus text-format metrics for:
- HTTP request count and latency
- RAG query outcomes
- ingestion job transitions
- rate-limit rejections

## Database Schema

### `knowledge_bases`
- `id uuid primary key`
- `name text unique`
- `description text`
- `created_at timestamptz`
- `updated_at timestamptz`

### `documents`
- `id uuid primary key`
- `knowledge_base_id uuid references knowledge_bases(id)`
- `file_name text`
- `mime_type text`
- `storage_key text`
- `checksum text`
- `status text`
- `metadata jsonb`
- `created_at timestamptz`
- `updated_at timestamptz`

### `document_chunks`
- `id uuid primary key`
- `document_id uuid references documents(id)`
- `chunk_index int`
- `content text`
- `token_count int`
- `section_title text`
- `page_number int`
- `metadata jsonb`
- `created_at timestamptz`

### `chunk_embeddings`
- `chunk_id uuid primary key references document_chunks(id)`
- `model_name text`
- `dimensions int`
- `embedding vector(256)`
- `created_at timestamptz`

### `ingestion_jobs`
- `id uuid primary key`
- `document_id uuid references documents(id)`
- `status text`
- `attempts int`
- `error_message text`
- `started_at timestamptz`
- `finished_at timestamptz`
- `created_at timestamptz`
- `updated_at timestamptz`

### `query_logs`
- `id uuid primary key`
- `knowledge_base_id uuid references knowledge_bases(id)`
- `question text`
- `normalized_question text`
- `answer_json jsonb` storing the full structured answer payload
- `cache_hit boolean`
- `latency_ms int`
- `created_at timestamptz`

### `query_citations`
- `id uuid primary key`
- `query_log_id uuid references query_logs(id)`
- `chunk_id uuid references document_chunks(id)`
- `rank int`
- `score float`

### Indexing notes
- Add `documents(knowledge_base_id, status)`.
- Add `document_chunks(document_id, chunk_index)`.
- Add a pgvector index on `chunk_embeddings.embedding`.
- Add optional `GIN` index on chunk metadata if filters become important.
- Add optional Postgres full-text search for hybrid retrieval.

## Implementation Plan by Milestones

### Milestone 1: Foundation
- Stand up FastAPI, SQLAlchemy, structured logging, settings, Docker Compose, and Postgres/Redis wiring.
- Add health/readiness endpoints and central error handling.

### Milestone 2: Upload and Async Ingestion
- Add document upload, filesystem storage, ingestion jobs, and Celery worker execution.
- Parse `txt`, `md`, `pdf`, and `docx`.

### Milestone 3: Chunking and Embeddings
- Add chunking strategy with overlap, embedding adapter, pgvector persistence, and indexing.
- Expose document status and job status APIs.

### Milestone 4: Retrieval and Grounded Answers
- Implement top-k retrieval, citation extraction, Redis response caching, and grounded answer assembly.
- Add query logging and debug metadata.

### Milestone 5: Hardening
- Add Alembic migrations, retry policies, failure handling, integration tests, load-test fixtures, and deployment notes.
- Swap local storage and deterministic embeddings for production providers.

## Local Development

1. Copy `.env.example` to `.env`.
2. If you are running locally without Docker, install dependencies with:

```bash
pip install -e .[dev]
```

3. Start the full stack:

```bash
docker compose up --build
```

4. Open the API docs at [http://localhost:8000/docs](http://localhost:8000/docs).
5. Open the frontend at [http://localhost:5173](http://localhost:5173).
6. Scrape metrics locally from [http://localhost:8000/metrics](http://localhost:8000/metrics).

### Running tests

If you have Python locally:

```bash
pytest
```

Inside Docker:

```bash
docker compose run --rm api pytest
```

### Important environment knobs
- `UPLOAD_RATE_LIMIT_PER_MINUTE`, `QUERY_RATE_LIMIT_PER_MINUTE`, `RETRIEVAL_RATE_LIMIT_PER_MINUTE`
- `DEFAULT_PAGE_SIZE`, `MAX_PAGE_SIZE`
- `ENQUEUE_RETRY_ATTEMPTS`, `ENQUEUE_RETRY_DELAY_SECONDS`, `ENQUEUE_RETRY_BACKOFF_MULTIPLIER`
- `INGESTION_TASK_MAX_RETRIES`, `INGESTION_TASK_RETRY_BACKOFF_SECONDS`
- `GROUNDED_ANSWER_MIN_CONFIDENCE`
- `EMBEDDING_PROVIDER`, `EMBEDDING_MODEL`, `EMBEDDING_DIMENSIONS`
- `LLM_PROVIDER`, `LLM_MODEL`, `LLM_TEMPERATURE`, `LLM_MAX_OUTPUT_TOKENS`
- `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `OPENAI_ORGANIZATION`, `OPENAI_PROJECT`
- `MODEL_REQUEST_TIMEOUT_SECONDS`, `MODEL_RETRY_ATTEMPTS`, `MODEL_RETRY_DELAY_SECONDS`, `MODEL_RETRY_BACKOFF_MULTIPLIER`

This scaffold is intentionally backend-first: the API contract, ingestion pipeline, persistence model, and operational concerns are in place before any frontend work.
