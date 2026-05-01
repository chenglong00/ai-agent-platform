"""Agent and tool configuration.

- **Gemini (chat)**: LangChain ``google_vertexai`` — uses Application Default Credentials (or Cloud Run SA).
  Set ``vertex_project`` and ``vertex_location``; grant that identity ``roles/aiplatform.user`` on that project.
  No ``GOOGLE_API_KEY`` required for this path.
- **Vertex AI Search**: ``tool_config.project_id`` may differ from ``vertex_project``. Grant the same SA
  **Discovery Engine** roles on the search project, e.g. ``roles/discoveryengine.user`` (includes
  ``discoveryengine.servingConfigs.search``) or ``roles/discoveryengine.editor``.

Workspace-backed (Drive/Workspace) datastores **do not support service-account Search**; see
``docs/VERTEX_AI_SEARCH.md``.
"""


class AgentSettings:
    funding_agent = {
        # Vertex AI Gemini (distinct project/region from Discovery Engine search if needed).
        "agent_config": {
            "model": "gemini-2.5-flash",
            "model_provider": "google_vertexai",
            "vertex_project": "sea-ml-hub",
            "vertex_location": "asia-southeast1",
            "temperature": 0,
            "max_output_tokens": 8192,
        },
        # Vertex AI Search (Discovery Engine) — all search tool settings live here only.
        "tool_config": {
            "funding_gemini_enterprise_gdrive_knowledge_base": {
                # Engine must NOT be Workspace-backed (Drive/Gmail): SA search returns 403 for those datastores.
                # IAM: SA needs roles/discoveryengine.user (or editor) on this project if using a key for that SA.
                # GCP project id *or* project number in the resource path (must match the console / curl URL).
                "project_id": "191471895730",
                # Engine region in the resource name (often ``global`` for multi-region apps).
                "location": "global",
                # Engine id from Vertex AI Search (exact string from the console URL — typos cause 404).
                "engine_id": "sales-ai-agent_1775112860548",
                "collection": "default_collection",
                # Serving config id from the engine (console often shows ``default_search``).
                "serving_config_id": "default_search",
                # Optional: full resource name; when set, overrides composed path below. Keep ``location`` in sync
                # with the ``.../locations/{location}/...`` segment (used for the regional Discovery API endpoint).
                "serving_config_resource": "",
                # Discovery request tuning.
                "default_page_size": 10,
                "summary_source_results": 5,
                # Optional: GCP project id for API quota billing with user ADC (defaults to project_id if unset).
                "quota_project_id": "",
            },
            "funding_vertex_ai_search_gdrive_knowledge_base": {
                # Engine must NOT be Workspace-backed (Drive/Gmail): SA search returns 403 for those datastores.
                # IAM: SA needs roles/discoveryengine.user (or editor) on this project if using a key for that SA.
                # GCP project id *or* project number in the resource path (must match the console / curl URL).
                "project_id": "16646144790",
                # Engine region in the resource name (often ``global`` for multi-region apps).
                "location": "global",
                # Engine id from Vertex AI Search (exact string from the console URL — typos cause 404).
                "engine_id": "funding-knowledge-base_1775186516898",
                "collection": "default_collection",
                # Serving config id from the engine (console often shows ``default_search``).
                "serving_config_id": "default_search",
                # Optional: full resource name; when set, overrides composed path below. Keep ``location`` in sync
                # with the ``.../locations/{location}/...`` segment (used for the regional Discovery API endpoint).
                "serving_config_resource": "",
                # Discovery request tuning.
                "default_page_size": 10,
                "summary_source_results": 5,
                # Optional: GCP project id for API quota billing with user ADC (defaults to project_id if unset).
                "quota_project_id": "",
            },
            "funding_knowledge_base": {
                # Engine must NOT be Workspace-backed (Drive/Gmail): SA search returns 403 for those datastores.
                # IAM: SA needs roles/discoveryengine.user (or editor) on this project if using a key for that SA.
                # GCP project id *or* project number in the resource path (must match the console / curl URL).
                "project_id": "16646144790",
                # Engine region in the resource name (often ``global`` for multi-region apps).
                "location": "global",
                # Engine id from Vertex AI Search (exact string from the console URL — typos cause 404).
                "engine_id": "funding-knowledgebase-gcs_1775187871173",
                "collection": "default_collection",
                # Serving config id from the engine (console often shows ``default_search``).
                "serving_config_id": "default_search",
                # Optional: full resource name; when set, overrides composed path below. Keep ``location`` in sync
                # with the ``.../locations/{location}/...`` segment (used for the regional Discovery API endpoint).
                "serving_config_resource": "",
                # Discovery request tuning.
                "default_page_size": 10,
                "summary_source_results": 5,
                # Optional: GCP project id for API quota billing with user ADC (defaults to project_id if unset).
                "quota_project_id": "",
            }
        },
    }

    code_review_agent = {
        "agent_config": {
            "model": "gemini-2.5-flash",
            "model_provider": "google_vertexai",
            "vertex_project": "sea-ml-hub",
            "vertex_location": "asia-southeast1",
            "temperature": 0,
            "max_output_tokens": 8192,
        },
    }

    deep_agent = {
        "agent_config": {
            "model": "gemini-2.5-flash",
            "model_provider": "google_vertexai",
            "vertex_project": "sea-ml-hub",
            "vertex_location": "asia-southeast1",
            "temperature": 0,
            "max_output_tokens": 8192,
            "recursion_limit": 50,
        },
    }
