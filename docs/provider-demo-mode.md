# Provider-Backed Demo Mode

Use this mode for public demos, recruiter walkthroughs, and any scenario where
you want semantically meaningful retrieval instead of the offline scaffold.

## Why this exists

The repository ships with a deterministic placeholder embedder and a placeholder
LLM path so the full RAG pipeline can run locally without external API
dependencies. That is useful for development, but it has one important tradeoff:

- the placeholder embedder does not perform real semantic similarity
- broad natural-language questions can retrieve weak chunks
- the system may return `unsupported` even when the document contains the answer

That behavior is correct for the confidence gate, but it is not the best public
demo experience. For recruiter-facing demos, switch to a real
OpenAI-compatible provider.

## Required environment changes

Update `.env`:

```env
EMBEDDING_PROVIDER=openai
LLM_PROVIDER=openai
OPENAI_API_KEY=your_key_here
OPENAI_BASE_URL=https://api.openai.com/v1
```

Keep the rest of your deployment unchanged unless your provider requires a
different base URL or model name.

## Why these changes were made

- `EMBEDDING_PROVIDER=openai`
  Reason: enables real semantic embeddings so retrieval quality matches the
  meaning of the question instead of a deterministic placeholder hash.

- `LLM_PROVIDER=openai`
  Reason: enables grounded answer generation over the retrieved context instead
  of the local extractive placeholder path.

- `OPENAI_API_KEY`
  Reason: required to authenticate to the provider.

- `OPENAI_BASE_URL`
  Reason: keeps the integration OpenAI-compatible, so the same code path can
  work with OpenAI or another provider that exposes the same API contract.

## After updating the provider

Restart the API and worker:

```bash
docker compose up -d --build api worker
```

Then re-upload the public demo documents into a fresh knowledge base so the
stored chunk embeddings are generated with the real provider rather than the
placeholder embedder.

## Recommended public demo flow

1. Create a fresh knowledge base.
2. Upload a technical document such as `architecture.md` or a compact design
   note.
3. Wait for ingestion to complete.
4. Run one success query and one rejection query.
5. Show citations, confidence, and rejection behavior in the demo video.
