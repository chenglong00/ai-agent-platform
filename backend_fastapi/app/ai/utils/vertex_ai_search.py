"""Vertex AI Search (Discovery Engine v1alpha): client, hit formatting, first-page markdown."""

import json
import logging
from typing import Any

from google.api_core import exceptions as google_exceptions
from google.api_core.client_options import ClientOptions
from google.cloud import discoveryengine_v1alpha as discoveryengine
from google.protobuf.json_format import MessageToDict

logger = logging.getLogger(__name__)

_clients: dict[tuple[str, str], discoveryengine.SearchServiceClient] = {}


def _client(location: str, quota_project_id: str | None) -> discoveryengine.SearchServiceClient:
    loc = (location or "global").strip() or "global"
    qp = (quota_project_id or "").strip()
    key = (loc, qp)
    if key not in _clients:
        kw: dict[str, str] = {}
        if loc != "global":
            kw["api_endpoint"] = f"{loc}-discoveryengine.googleapis.com"
        if qp:
            kw["quota_project_id"] = qp
        opts = ClientOptions(**kw) if kw else None
        _clients[key] = discoveryengine.SearchServiceClient(client_options=opts)
    return _clients[key]


def _proto_to_jsonable(obj: Any) -> Any:
    if obj is None or isinstance(obj, (bool, int, float, str)):
        return obj
    if isinstance(obj, dict):
        return {str(k): _proto_to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_proto_to_jsonable(x) for x in obj]
    if isinstance(obj, (bytes, bytearray)):
        return obj.decode("utf-8", errors="replace")
    pb = getattr(obj, "_pb", None)
    if pb is not None:
        try:
            return _proto_to_jsonable(MessageToDict(pb))
        except Exception:
            pass
    name = type(obj).__name__
    if name in ("RepeatedComposite", "RepeatedScalarContainer"):
        return [_proto_to_jsonable(x) for x in obj]
    if name == "MapComposite" or hasattr(obj, "items"):
        try:
            return {str(k): _proto_to_jsonable(v) for k, v in obj.items()}
        except (TypeError, AttributeError, ValueError):
            pass
    try:
        return _proto_to_jsonable(MessageToDict(obj))
    except Exception:
        return str(obj)


def _derived_struct_payload(derived: Any) -> dict | None:
    if derived is None:
        return None
    if hasattr(derived, "fields"):
        if not derived.fields:
            return None
        out = MessageToDict(derived)
    else:
        try:
            out = dict(derived)
        except (TypeError, ValueError):
            try:
                out = MessageToDict(derived)
            except Exception:
                return None
    if not out:
        return None
    cleaned = _proto_to_jsonable(out)
    return cleaned if isinstance(cleaned, dict) else None


def _hit_plain_text(hit: discoveryengine.SearchResponse.SearchResult) -> str:
    parts: list[str] = []
    if hit.chunk and hit.chunk.content:
        parts.append(hit.chunk.content.strip())
    if hit.document:
        doc = hit.document
        if doc.json_data:
            parts.append(doc.json_data.strip())
        else:
            payload = _derived_struct_payload(doc.derived_struct_data)
            if payload is not None:
                parts.append(json.dumps(payload, ensure_ascii=False))
    return "\n".join(p for p in parts if p) or ""


def _first_page_markdown(
    pager: discoveryengine.services.search_service.pagers.SearchPager,
) -> str:
    """Use ``pager.pages`` (full ``SearchResponse``); ``iter(pager)`` yields only ``SearchResult`` rows."""
    try:
        page = next(pager.pages)
    except StopIteration:
        return "No response from search."

    lines: list[str] = []
    if getattr(page, "corrected_query", None):
        cq = page.corrected_query.strip()
        if cq:
            lines.append(f"*(Spell-corrected query used: {cq})*\n")

    summary = getattr(page, "summary", None)
    if summary is not None:
        st = (getattr(summary, "summary_text", None) or "").strip()
        if st:
            lines.append("## Summary\n" + st)
        elif getattr(summary, "summary_skipped_reasons", None):
            reasons = ", ".join(
                discoveryengine.SearchResponse.Summary.SummarySkippedReason(r).name
                for r in summary.summary_skipped_reasons
            )
            lines.append(f"## Summary\n*(Skipped: {reasons})*")

    blocks: list[str] = []
    for i, hit in enumerate(page.results, 1):
        text = _hit_plain_text(hit)
        blocks.append(f"### Result {i}\n{text}" if text else f"### Result {i}\n*(no retrievable text)*")

    if blocks:
        lines.append("## Snippets\n\n" + "\n\n".join(blocks))
    elif not lines:
        return "No results for this query."

    return "\n\n".join(lines)


def run_discovery_search_markdown(
    location: str,
    request: discoveryengine.SearchRequest,
    *,
    quota_project_id: str | None = None,
) -> str:
    """Run search and return markdown for the first response page."""
    try:
        pager = _client(location, quota_project_id).search(request)
    except google_exceptions.GoogleAPICallError as e:
        err = str(e)
        logger.warning(
            "vertex_search failed serving_config=%s %s",
            getattr(request, "serving_config", None) or "(missing)",
            e,
        )
        if "workspace" in err.lower() and "service account" in err.lower():
            return (
                "Search unavailable: this engine uses a Workspace (Drive/Gmail/etc.) datastore. "
                "Google does not allow Discovery Search with a service account for those stores. "
                "Point the tool at an engine backed by unstructured/GCS/website/BigQuery data, "
                "or use user OAuth (not typical for a server agent)."
            )
        el = err.lower()
        if (
            "iam_permission_denied" in el
            or "permission denied" in el
        ) and "discoveryengine" in el:
            return (
                "Search unavailable (IAM): the service account needs Discovery Engine access on the "
                "project that owns this engine — e.g. roles/discoveryengine.user or "
                "roles/discoveryengine.editor on that GCP project (permission "
                "discoveryengine.servingConfigs.search). Confirm the engine/servingConfig path matches "
                "the console."
            )
        if "dataconnector" in el and "not found" in el:
            return (
                "Search unavailable (configuration): the engine’s data store references a "
                "DataConnector that does not exist (deleted, wrong collection id, or sync not created). "
                "In Vertex AI Search / Agent Builder, open the linked data store "
                "(e.g. gdrive-funding-datastore_…) and fix or recreate the connector, or attach a valid "
                "data store to this engine."
            )
        return f"Search request failed: {e}"
    except Exception as e:
        logger.exception("vertex_search unexpected")
        return f"Search failed: {e}"

    return _first_page_markdown(pager)
