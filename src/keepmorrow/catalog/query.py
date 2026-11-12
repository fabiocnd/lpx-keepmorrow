"""Bounded deterministic catalog browsing and literal text search."""

from __future__ import annotations

from itertools import chain

from .model import CatalogError, CatalogLimits, Document, effective_associations, encoded_size, json_bytes


def _bounded_result(document: Document, limits: CatalogLimits) -> Document:
    encoded_size(document, limits.max_response_bytes)
    return document


def browse_catalog(
    document: Document, *, offset: int = 0, limit: int = 50,
    project_id: str | None = None, association_state: str | None = None,
    limits: CatalogLimits | None = None,
) -> Document:
    active = limits or CatalogLimits()
    if type(offset) is not int or offset < 0 or type(limit) is not int or not 1 <= limit <= active.max_results:
        raise CatalogError("Catalog pagination is outside its supported range.")
    if association_state is not None and (not isinstance(association_state, str) or association_state not in {
            "project_confirmed", "standalone_confirmed", "association_unknown"}):
        raise CatalogError("The association filter is unsupported.")
    if project_id is not None and (not isinstance(project_id, str) or not project_id.strip()):
        raise CatalogError("The project filter requires a nonempty identifier string.")
    associations = effective_associations(document)
    selected = [item for item in document["conversations"]
                if (project_id is None or associations[item["conversation_key"]]["project_id"] == project_id)
                and (association_state is None or associations[item["conversation_key"]]["state"] == association_state)]
    results = []
    response_bytes = 1024
    for item in selected[offset:offset + limit]:
        entry = {"conversation_key": item["conversation_key"], "source_id": item["source_id"],
                        "association": {key: associations[item["conversation_key"]][key]
                                        for key in ("state", "project_id")},
                        "revision_count": len(item["revisions"]),
                        "revisions_truncated": len(item["revisions"]) > 20,
                        "revisions": [{"revision_id": revision["revision_id"], "title": revision["title"][:512],
                                       "title_truncated": len(revision["title"]) > 512,
                                       "node_count": len(revision["nodes"]),
                                       "occurrence_count": len(revision["occurrences"])}
                                      for revision in item["revisions"][:20]]}
        encoded_size = len(json_bytes(entry))
        if response_bytes + encoded_size > active.max_response_bytes:
            if not results:
                raise CatalogError("The response budget is too small for one catalog entry.")
            break
        response_bytes += encoded_size
        results.append(entry)
    return _bounded_result({"total": len(selected), "offset": offset, "limit": limit, "items": results,
                            "next_offset": offset + len(results) if offset + len(results) < len(selected) else None}, active)


def search_catalog(
    document: Document, query: str, *, limit: int = 20, conversation_key: str | None = None,
    limits: CatalogLimits | None = None,
) -> Document:
    """Search all retained revisions literally; input is never regex or executable.

    O(T) scanning is explicit for this bounded local milestone. Returned text is
    user-requested result content, not operational telemetry or an AI summary.
    """
    active = limits or CatalogLimits()
    if not isinstance(query, str) or not query.strip() or len(query) > active.max_query_characters:
        raise CatalogError("Search requires a nonempty query within its character limit.")
    if type(limit) is not int or not 1 <= limit <= active.max_results:
        raise CatalogError("The search result limit is outside its supported range.")
    if conversation_key is not None and not any(item["conversation_key"] == conversation_key
                                                for item in document["conversations"]):
        raise CatalogError("The selected conversation is absent from the collection.")
    needle = query.casefold()
    results: list[Document] = []
    response_bytes = 1024
    for conversation in document["conversations"]:
        if conversation_key is not None and conversation["conversation_key"] != conversation_key:
            continue
        for revision in conversation["revisions"]:
            candidates = chain(((None, revision["title"]),),
                               ((node["id"], node["text"]) for node in revision["nodes"]))
            for node_id, text in candidates:
                if needle not in text.casefold():
                    continue
                if len(results) == limit:
                    return _bounded_result({"items": results, "truncated": True, "limit": limit}, active)
                result = {"conversation_key": conversation["conversation_key"],
                                "revision_id": revision["revision_id"], "node_id": node_id,
                                "title": revision["title"][:512], "title_truncated": len(revision["title"]) > 512,
                                "excerpt": text[:240], "excerpt_truncated": len(text) > 240}
                encoded_size = len(json_bytes(result))
                if response_bytes + encoded_size > active.max_response_bytes:
                    if not results:
                        raise CatalogError("The response budget is too small for one search result.")
                    return _bounded_result({"items": results, "truncated": True, "limit": limit}, active)
                response_bytes += encoded_size
                results.append(result)
    return _bounded_result({"items": results, "truncated": False, "limit": limit}, active)


def read_revision(
    document: Document, conversation_key: str, *, revision_id: str | None = None,
    offset: int = 0, limit: int = 50, limits: CatalogLimits | None = None,
) -> Document:
    """Return a bounded graph page, explicitly identifying omitted text or edges."""
    active = limits or CatalogLimits()
    if type(offset) is not int or offset < 0 or type(limit) is not int or not 1 <= limit <= active.max_results:
        raise CatalogError("Revision pagination is outside its supported range.")
    conversation = next((item for item in document["conversations"]
                         if item["conversation_key"] == conversation_key), None)
    if conversation is None:
        raise CatalogError("The selected conversation is absent from the collection.")
    if revision_id is None:
        positions = {capture["capture_id"]: index for index, capture in enumerate(document["captures"])}
        revision = max(conversation["revisions"], key=lambda item: max(
            (positions[value["capture_id"]], value["provenance"]["record_index"])
            for value in item["occurrences"]))
        selection_basis = "most_recently_supplied_occurrence"
    else:
        revision = next((item for item in conversation["revisions"] if item["revision_id"] == revision_id), None)
        if revision is None:
            raise CatalogError("The selected revision is absent from the conversation.")
        selection_basis = "explicit_revision"
    response: Document = {
        "conversation_key": conversation_key, "revision_id": revision["revision_id"],
        "title": revision["title"][:512], "title_truncated": len(revision["title"]) > 512,
        "selection_basis": selection_basis, "offset": offset, "limit": limit,
        "total_nodes": len(revision["nodes"]), "nodes": [],
        "revision_ids": [item["revision_id"] for item in conversation["revisions"][:200]],
        "revision_ids_truncated": len(conversation["revisions"]) > 200,
    }
    response_bytes = len(json_bytes(response)) + 512
    for node in revision["nodes"][offset:offset + limit]:
        result = {field: node[field] for field in ("id", "parent_id", "message_id", "role", "content_type")}
        result.update({"text": node["text"][:4096], "text_truncated": len(node["text"]) > 4096,
                       "children_ids": node["children_ids"][:32], "child_count": len(node["children_ids"]),
                       "children_truncated": len(node["children_ids"]) > 32})
        encoded_size = len(json_bytes(result))
        if response_bytes + encoded_size > active.max_response_bytes:
            if not response["nodes"]:
                raise CatalogError("The response budget is too small for one message node.")
            break
        response_bytes += encoded_size
        response["nodes"].append(result)
    next_offset = offset + len(response["nodes"])
    response["next_offset"] = next_offset if next_offset < len(revision["nodes"]) else None
    return _bounded_result(response, active)
