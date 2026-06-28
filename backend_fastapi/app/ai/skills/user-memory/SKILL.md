---
name: user-memory
description: Extract and save durable facts, preferences, and profile details about the user into long-term memory.
---

# User Memory

Use this skill when the conversation reveals **stable** information about the user that would help in future chats.

## What to remember

| Category | Examples |
|----------|----------|
| **fact** | Job title, team, location, tech stack, company name |
| **preference** | Communication style, favorite tools, language, formatting likes/dislikes |
| **profile** | Name they prefer, role, expertise level, recurring projects |
| **goal** | Ongoing objectives ("migrating to Postgres", "building a RAG pipeline") |
| **other** | Anything durable that does not fit above |

## Extraction workflow

1. **During the chat** — when the user states something clearly meant to persist ("remember that…", "I always…", "my name is…"), call `save_user_memory` immediately with the right category.
2. **After helping them** — if the turn surfaced new stable facts or preferences you did not save yet, call `save_user_memory` before finishing your reply.
3. **Before assuming** — call `search_user_memories` or `list_user_memories` if you need to recall what you already know.
4. **Keep entries atomic** — one fact or preference per save; short declarative sentences.

## Do not save

- One-off task details ("create index.html today")
- Secrets (passwords, API keys, tokens)
- Hypotheticals or guesses
- Information the user asked you to forget

## Do not

- Tell the user you updated memory unless they asked you to remember something.
- Duplicate entries — if similar memory exists, saving again updates it.
