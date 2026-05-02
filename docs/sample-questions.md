# Sample Questions

Use these questions in the live demo, README, LinkedIn post, and recruiter
walkthrough so people can test the project quickly without guessing.

## Best Starter Questions

1. **How should asynchronous document ingestion be structured in this system?**
   - Good for showing worker-based ingestion, queueing, and citations.

2. **What do the indexed documents say about API reliability and worker-based processing?**
   - Good for showing retrieval across multiple chunks or documents.

3. **What architecture tradeoffs are described around background jobs and retrieval?**
   - Good for showing synthesis across retrieved evidence.

4. **How does the system prevent unsupported answers from being returned?**
   - Good for demonstrating confidence thresholding and grounded behavior.

5. **What evidence is cited for the recommended ingestion design?**
   - Good for highlighting source transparency and chunk-level citations.

## Recruiter-Friendly Version

If the reviewer is less technical, guide them to these:

- `How does this system process uploaded documents?`
- `What does the system say about reliable backend processing?`
- `How are answers grounded in the uploaded documents?`

## Questions To Avoid In The Demo

Avoid prompts that:

- are too broad for the sample documents
- require knowledge outside the uploaded content
- look like generic interview questions instead of document-based retrieval

## Best Public Demo Pattern

When sharing the live link publicly, include 2 to 3 sample prompts right under
the demo link so a recruiter can test it immediately.

Example:

```text
Try asking:
- How should asynchronous ingestion be structured in this system?
- What tradeoffs are mentioned around worker-based processing?
- How does the system keep answers grounded in the source documents?
```
