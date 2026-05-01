# Vertex AI Search (Discovery Engine) and the funding agent

The funding agent can call **`funding_knowledge_base`**, which uses the Discovery Engine **Search** API. Settings live in `app/ai/config.py` under `AgentSettings.funding_agent["tool_config"]["funding_knowledge_base"]` (project id, location, `engine_id`, `serving_config_id`, optional `serving_config_resource`, `quota_project_id`).

The HTTP client and error handling are in `app/ai/utils/vertex_ai_search.py`.

## Authentication: service account vs user

In Docker and typical server deployments, the app uses **Application Default Credentials** from a **service account JSON** (`GOOGLE_APPLICATION_CREDENTIALS`).

A **user** token (for example from `gcloud auth print-access-token` after `gcloud auth login`) is a **different principal** and may be allowed when a **service account** is not.

To debug with the same identity as production:

```bash
cd backend_fastapi
export KEY_FILE="/Users/chenglong/Projects/ai-application-platform/backend_fastapi/secrets/cm-sales-ai-agent-sa.json"
export TOKEN=$(uv run python -c "
from google.oauth2 import service_account
from google.auth.transport.requests import Request
scopes = ['https://www.googleapis.com/auth/cloud-platform']
c = service_account.Credentials.from_service_account_file('$KEY_FILE', scopes=scopes)
c.refresh(Request())
print(c.token)
")
# Then POST to .../servingConfigs/YOUR_CONFIG:search with Authorization: Bearer $TOKEN
curl -X POST -H "Authorization: Bearer $TOKEN" \
-H "Content-Type: application/json" \
"https://discoveryengine.googleapis.com/v1alpha/projects/16646144790/locations/global/collections/default_collection/engines/funding-knowledgebase-gcs_1775187871173/servingConfigs/default_search:search" \
-d '{"query":"tell me about aws funding","pageSize":10,"queryExpansionSpec":{"condition":"AUTO"},"spellCorrectionSpec":{"mode":"AUTO"},"languageCode":"en-GB","contentSearchSpec":{"extractiveContentSpec":{"maxExtractiveAnswerCount":1}},"userInfo":{"timeZone":"Asia/Singapore"}}'

```

Or: `gcloud auth activate-service-account --key-file=...` then `gcloud auth print-access-token`.

Run these commands from **`backend_fastapi`** so `uv run` resolves dependencies that include `google-auth`. Do not use `frontend_nextjs` for that Python snippet.

## Workspace datastores: service accounts are not supported

If the Search API returns:

```text
403 PERMISSION_DENIED
Search using service account credentials is not supported for workspace datastores.
```

then the engine is backed by a **Workspace-style** data source (for example **Google Drive / Google Workspace** indexing). **Google does not allow Search with a service account** for those datastores. **IAM roles such as `roles/discoveryengine.user` do not override this.**

Implications:

- **`gcloud auth print-access-token` (user)** may succeed for the same `:search` URL while **SA + curl** fails with the message above.
- A **server-side agent** using only a mounted SA key **cannot** use that engine for search until you change the data architecture.

**Ways forward:**

1. **Non-Workspace data (recommended for SA + Docker)**  
   Add or use a data store fed by **Cloud Storage, BigQuery, website crawl, or unstructured document import**, attach it to an engine, and point `tool_config` at that engine.

2. **Keep Workspace / Drive as the only source**  
   Implement **per-user OAuth** and call Search with **user credentials**, not the service account. This is a different security and product design than a shared SA in the API container.

3. **Disable the tool temporarily**  
   Set **`FUNDING_KB_SEARCH_ENABLED=false`** in environment (see `app/core/config.py`). The agent still runs; the knowledge-base tool is omitted and the system prompt is adjusted in `app/ai/agents/funding_agent.py`.

## IAM when the datastore is *not* Workspace-blocked

If Search fails with **`discoveryengine.servingConfigs.search`** denied (**`IAM_PERMISSION_DENIED`**), grant the **same** service account used in production a role on the **GCP project that owns the engine** (the project in the resource path, which may differ from `vertex_project` used for Gemini), for example:

- `roles/discoveryengine.user`, or  
- `roles/discoveryengine.editor`

Wait a minute or two after IAM changes.

## DataConnector not found (404)

A response like **`DataConnector .../dataConnector not found`** means the engine’s data store references a connector resource that is missing or never provisioned. Fix this in **Vertex AI Search / Agent Builder** (recreate the connector, fix the data store id, or attach a valid store to the engine)—not in application code.

## Gemini vs Discovery project

**Gemini (Vertex)** uses `vertex_project` / `vertex_location` in `agent_config`. **Discovery Search** uses `tool_config.project_id` (and related fields). The same service account may need **`roles/aiplatform.user`** on the Gemini project and **`roles/discoveryengine.user`** on the Discovery project if those projects differ.

## Related files

| File | Role |
|------|------|
| `app/ai/config.py` | Engine paths and tuning |
| `app/ai/tools/search.py` | Builds `SearchRequest` |
| `app/ai/utils/vertex_ai_search.py` | RPC, markdown formatting, friendly error strings |
| `app/ai/agents/funding_agent.py` | Registers tools; respects `FUNDING_KB_SEARCH_ENABLED` |
| `app/core/config.py` | `FUNDING_KB_SEARCH_ENABLED` |
| `docker-compose.yml` | `GOOGLE_APPLICATION_CREDENTIALS` mount for the API container |
