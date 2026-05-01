from google.cloud import discoveryengine_v1alpha as discoveryengine
from langchain.tools import tool

from app.ai.config import AgentSettings
from app.ai.utils.vertex_ai_search import run_discovery_search_markdown

# Discovery Engine summary model (include_citations=True) — tuned for partner funding KB.
_SEARCH_SUMMARY_PREAMBLE = (
    "You summarize search results about AWS partner funding and Google Cloud (GCP) funding programs.\n"
    "- Use only information supported by the retrieved passages; do not invent eligibility, amounts, or deadlines.\n"
    "- Align claims with the cited snippets; paraphrase when helpful.\n"
    "- If the results are insufficient or contradictory, say so briefly and report what was found.\n"
    "- Prefer short paragraphs or bullets; stay factual and concise."
)

# Tool schema text — keep aligned with app/ai/prompts/funding_agent.md.
_FUNDING_KB_TOOL_DESCRIPTION = (
    "Search the internal knowledge base (Vertex AI Search / Discovery Engine). "
    "Indexed content emphasizes AWS partner funding and Google Cloud (GCP) funding programs—eligibility, "
    "benefits, processes, and related partner economics—plus supporting account and sales context where present. "
    "Returns a short model-generated summary (when the query is summary-seeking) plus ranked "
    "snippets/passages. Use focused natural-language queries; rephrase or run again with broader "
    "terms if results are thin."
)


@tool(description=_FUNDING_KB_TOOL_DESCRIPTION)
def funding_knowledge_base(search_query: str) -> str:
    """Query the configured Vertex AI Search engine for AWS/GCP partner funding knowledge."""
    q = search_query.strip()
    if not q:
        return "Empty search query."

    cfg = AgentSettings.funding_agent["tool_config"]["funding_knowledge_base"]
    fallback_location = str(cfg.get("location") or "global").strip() or "global"

    page_size = int(cfg["default_page_size"])
    summary_result_count = int(cfg["summary_source_results"])
    quota_project = str(cfg.get("quota_project_id") or "").strip() or str(
        cfg.get("project_id") or ""
    ).strip() or None

    location = fallback_location
    override = str(cfg.get("serving_config_resource") or "").strip()
    if override:
        serving_config = override
    else:
        project_id = str(cfg["project_id"] or "").strip()
        engine_id = str(cfg["engine_id"] or "").strip()
        collection = str(cfg.get("collection") or "default_collection").strip() or "default_collection"
        serving_id = str(cfg.get("serving_config_id") or "default_search").strip() or "default_search"
        serving_config = (
            f"projects/{project_id}/locations/{location}/collections/{collection}/"
            f"engines/{engine_id}/servingConfigs/{serving_id}"
        )

    content_search_spec = discoveryengine.SearchRequest.ContentSearchSpec(
        snippet_spec=discoveryengine.SearchRequest.ContentSearchSpec.SnippetSpec(
            return_snippet=True,
        ),
        summary_spec=discoveryengine.SearchRequest.ContentSearchSpec.SummarySpec(
            summary_result_count=summary_result_count,
            include_citations=True,
            ignore_adversarial_query=True,
            ignore_non_summary_seeking_query=True,
            model_prompt_spec=discoveryengine.SearchRequest.ContentSearchSpec.SummarySpec.ModelPromptSpec(
                preamble=_SEARCH_SUMMARY_PREAMBLE,
            ),
            model_spec=discoveryengine.SearchRequest.ContentSearchSpec.SummarySpec.ModelSpec(
                version="stable",
            ),
        ),
    )

    request = discoveryengine.SearchRequest(
        serving_config=serving_config,
        query=q,
        page_size=page_size,
        content_search_spec=content_search_spec,
        query_expansion_spec=discoveryengine.SearchRequest.QueryExpansionSpec(
            condition=discoveryengine.SearchRequest.QueryExpansionSpec.Condition.AUTO,
        ),
        spell_correction_spec=discoveryengine.SearchRequest.SpellCorrectionSpec(
            mode=discoveryengine.SearchRequest.SpellCorrectionSpec.Mode.AUTO,
        ),
    )

    return run_discovery_search_markdown(location, request, quota_project_id=quota_project)
