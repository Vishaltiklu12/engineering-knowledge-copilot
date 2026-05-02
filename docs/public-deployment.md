# Public Deployment Guide

This project is best deployed publicly as a **single Docker Compose stack on one
Ubuntu VM**. That fits the current architecture well because the API and worker
both depend on the same uploaded-document lifecycle.

## Why This Deployment Model

The current backend includes:

- FastAPI API service
- Celery worker
- Redis
- PostgreSQL + pgvector
- local uploaded files shared across ingestion and retrieval

For a recruiter-facing demo, a single VM is the most reliable path because it
keeps the storage, worker, and API behavior close to local development.

## Recommended Hosting

- Ubuntu VM on DigitalOcean, Hetzner, Linode, or similar
- 2 vCPU / 4 GB RAM is enough for a recruiter demo
- 40 GB disk is usually sufficient for a small sample dataset

## 1. Provision the Server

Create an Ubuntu server and note:

- public IP
- SSH key or password
- domain or subdomain you want to point to it later

## 2. Install Docker

SSH into the server:

```bash
ssh root@YOUR_SERVER_IP
```

Install Docker Engine and Docker Compose plugin using Docker's official Ubuntu
installation guide.

## 3. Clone the Repository

```bash
git clone https://github.com/Vishaltiklu12/engineering-knowledge-copilot.git
cd engineering-knowledge-copilot
```

## 4. Configure Environment Variables

```bash
cp .env.example .env
```

### Minimum demo config

The placeholder mode works without external model credentials:

```env
EMBEDDING_PROVIDER=placeholder
LLM_PROVIDER=placeholder
```

### Optional real model config

If you want live provider-backed answers:

```env
EMBEDDING_PROVIDER=openai
LLM_PROVIDER=openai
OPENAI_API_KEY=your_key_here
OPENAI_BASE_URL=https://api.openai.com/v1
```

## 5. Start the Stack

```bash
docker compose up -d --build
```

## 6. Verify the Demo

Check the API docs:

- `http://YOUR_SERVER_IP:8000/docs`
- `http://YOUR_SERVER_IP:8000/metrics`

Check container health:

```bash
docker compose ps
docker compose logs api --tail=100
docker compose logs worker --tail=100
```

## 7. Seed the Demo

Before sharing publicly:

1. Create a knowledge base
2. Upload 2 to 5 sample engineering documents
3. Wait for ingestion to complete
4. Run a few sample queries
5. Confirm citations are visible and readable

## 8. Make It Recruiter-Friendly

Keep the first public version simple:

- share the repo link
- share the `/docs` URL
- preload documents so no setup is required from a recruiter
- provide 3 sample questions from [sample-questions.md](./sample-questions.md)

## 9. Add HTTPS Later

Once the demo works publicly, add:

- a domain or subdomain
- reverse proxy
- HTTPS

The clean next step is to put **Caddy** or **Nginx** in front of the API.

## Suggested Public URLs

- `https://copilot.yourdomain.com/docs`
- `https://demo.yourdomain.com/docs`

## What To Avoid In The First Public Release

- open public uploads with no controls
- unbounded public usage
- exposing debug-only workflows to recruiters
- changing the architecture just to fit a static hosting platform
