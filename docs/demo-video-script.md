# 30 to 60 Second Demo Script

Use this script for a LinkedIn clip, Loom video, or portfolio walkthrough.

## Goal

Show that this is a **backend-first RAG system** with real ingestion, retrieval,
and grounding behavior, not just a prompt wrapper.

## Demo Length

- target: **45 seconds**
- acceptable range: **30 to 60 seconds**

## Recording Setup

Have these ready before recording:

- live demo running
- knowledge base already created
- sample documents already ingested
- one tested sample question
- repo URL copied

## Screen Flow

### 0 to 5 seconds

Show title card or browser tab:

`Engineering Knowledge Copilot`

Say:

> I built an Engineering Knowledge Copilot, a backend-first RAG system for technical document retrieval and grounded question answering.

### 5 to 15 seconds

Show API docs or UI and mention the stack:

- FastAPI
- PostgreSQL + pgvector
- Redis
- Celery
- Docker

Say:

> I wanted to build this like a production backend instead of a simple chat-with-PDF demo.

### 15 to 30 seconds

Show the ingestion flow:

- knowledge base already exists
- document upload or existing uploaded document
- ingestion job status

Say:

> Documents are uploaded, parsed, chunked, embedded, and indexed through an asynchronous ingestion pipeline.

### 30 to 50 seconds

Run one sample query.

Recommended prompt:

> How should asynchronous document ingestion be structured in this system?

Show:

- answer
- citations
- confidence
- follow-up questions

Say:

> The system retrieves top-k relevant chunks and returns grounded answers with citations instead of unverified output.

### 50 to 60 seconds

Show:

- GitHub repo
- architecture diagram or README

Say:

> This project helped me go deeper on backend system design, retrieval pipelines, and production-minded AI application engineering.

## Best On-Screen Captions

Use 3 to 4 short captions at most:

- `Async ingestion pipeline`
- `pgvector retrieval`
- `Grounded answers with citations`
- `FastAPI + Redis + Celery + Docker`

## Recording Tips

- Keep cursor movement slow
- Zoom browser to 110% or 125%
- Use one clean sample query
- Do not spend time typing long values on screen
- Keep the clip product-focused, not tool-focused
