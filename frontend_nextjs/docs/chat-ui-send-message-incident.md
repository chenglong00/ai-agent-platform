# Chat UI: “Send” did not POST messages (incident notes)

## Issue summary

The chat UI could load conversations and create a new conversation, but clicking **Send** did not reliably send a chat message from the browser.

**Symptoms**

- Login worked  
- Conversation list worked  
- Creating a conversation worked  
- Backend API worked when tested directly with `curl`  
- From the browser there was often **no POST** to the message endpoint (`.../conversations/{id}/messages`)

## Root causes (frontend-heavy)

The failure was mostly in the **frontend path between “user clicked Send” and `fetch`**, not in Docker, FastAPI, or Postgres themselves—though a few deployment issues showed up in parallel.

### 1. Temporary message IDs (`crypto.randomUUID`)

After a conversation existed (or was just created), the chat page generated optimistic UI rows using temporary IDs, roughly:

```ts
const tempUserId = `pending-user:${crypto.randomUUID()}`
const tempAssistantId = `pending-assistant:${crypto.randomUUID()}`
```

`crypto.randomUUID()` is not guaranteed to behave the same in every runtime. Depending on **browser, version, and context** (e.g. non-HTTPS origins, extensions, or unusual embeds), calling it can throw or be missing, which stops the rest of the submit handler before `sendChatMessage(...)` runs—so **no POST** appears in the Network tab.

### 2. `PromptInput`: `onSubmit` gated on async attachment work

`PromptInput` only called the parent `onSubmit` **after** `Promise.all(...)` finished converting `blob:` attachment URLs. If that work never settled (stuck `fetch`, bad blob state), **`onSubmit` never ran** → again, no POST even with text in the box.

**Fix:** If there are no `blob:` URLs, call `onSubmit` immediately; if there are, use a timeout fallback so submit is not blocked forever.

### 3. Form text capture (`FormData` + `display: contents`)

With `PromptInputBody` using `display: contents`, some browsers omit the message field from `FormData`, so the resolved text was empty and the handler returned early without calling the API.

**Fix:** `PromptInputProvider` (controlled text), `resolveMessageText()` fallbacks (FormData → `textarea[name="message"]`), and a non–`display: contents` wrapper on `PromptInputBody`.

## Why it looked like “backend / Docker”

Evidence pointed away from the API implementation:

1. `curl` to `POST .../conversations/{id}/messages` succeeded.  
2. Request/response shapes matched the frontend helpers.  
3. Network showed `POST /conversations`, `GET .../messages`, etc., but **no** `POST .../messages` when the bug triggered.

That pattern means: **stop before the wire**—event handler, state, or a thrown exception in client code.

## Resolution (code)

### Safe temporary IDs

Replace direct `crypto.randomUUID()` with a helper that falls back when `randomUUID` is unavailable:

```ts
function makeTempId(prefix: string): string {
  if (typeof globalThis !== "undefined" && globalThis.crypto?.randomUUID) {
    return `${prefix}:${globalThis.crypto.randomUUID()}`
  }
  return `${prefix}:${Date.now()}-${Math.random().toString(36).slice(2)}`
}

const tempUserId = makeTempId("pending-user")
const tempAssistantId = makeTempId("pending-assistant")
```

### Other frontend changes (same effort)

- **`src/app/api/v1/[...path]/route.ts`**: explicit Next → FastAPI proxy (body + `Authorization`) for `/api/v1/*`.  
- **Docker Compose `web`**: `BACKEND_PROXY_TARGET=http://api:8000` at **runtime** for that route.  
- **`docker-compose.yml`**: do not override `ALLOWED_ORIGINS` in `api.environment` so `backend_fastapi/.env` CORS values apply when the browser calls the API directly.  
- **`parseApiErrorMessage`** in chat API helpers so 401/502 copy is not login-form–specific.

## Backend / ops issues that surfaced separately

- **`IsADirectoryError: ... gcp-sa.json is a directory`**: host bind-mount path missing or wrong; Docker created a directory at the mount target → Vertex auth broke until a real JSON **file** was mounted.  
- **Uvicorn access logs**: `uvicorn.access` is set to **WARNING** in app logging config, so routine `POST` lines often do not appear in `docker compose logs`; use browser Network or temporary log-level changes for request tracing.

## Final outcome

After the frontend fixes and a correct **`web`** rebuild:

- The browser issues **POST** `.../messages` when Send is used.  
- The backend returns assistant text when Vertex credentials and IAM are correct.

## Key lessons

- **No network request** → suspect **client** first: handlers, guards, thrown errors, `Promise` chains that never resolve.  
- **`curl` works, UI does not** → backend route is usually fine; compare URL (same-origin `:3000` vs direct `:8000`), CORS, proxy, and token.  
- **Distinguish** “request never sent” from “request sent but 401/502/503”—DevTools **POST** row and status code decide.

## Short blurb (for README / runbooks)

> Chat Send sometimes never called the API because client-side code could throw or stall before `sendChatMessage`: e.g. `crypto.randomUUID()` or attachment `Promise.all` blocked `onSubmit`, or empty text from `FormData` quirks. The backend `POST .../messages` endpoint was fine when exercised with `curl`. Fixes: `makeTempId` fallback, immediate `onSubmit` when there are no `blob:` attachments (with timeout otherwise), controlled prompt input / textarea fallbacks, and an explicit `/api/v1` BFF proxy plus `BACKEND_PROXY_TARGET` on the `web` container.

## Optional: formal incident report sections

If you need a stricter template, add: **Problem**, **Impact**, **Timeline**, **Root cause**, **Fix**, **Verification**, **Prevention** (CI smoke test for Send, staging over same URL shape as prod, etc.).
