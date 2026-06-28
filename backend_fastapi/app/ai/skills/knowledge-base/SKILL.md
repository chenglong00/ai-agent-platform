---
name: knowledge-base
description: Search ingested PDFs and internal documents via the knowledge base before answering policy or reference questions.
---

# Knowledge Base

Use this skill when the user asks about uploaded documents, internal policies, handbooks, or reference material stored in the knowledge base.

## Workflow

1. Call `search_knowledge_base` with a focused query derived from the user's question.
2. Base your answer on returned excerpts; cite document titles when possible.
3. If no excerpts are found, say so and ask whether documents need to be uploaded and indexed first.

## Do not

- Guess content that was not returned by search.
- Skip search for questions that clearly depend on internal or uploaded documents.
