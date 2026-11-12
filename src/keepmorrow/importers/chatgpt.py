"""Interpret a bounded experimental ChatGPT mapping profile from preserved files.

This adapter is not a specification of every ChatGPT export. Source bytes remain
authoritative; the derived graph only describes fields recognized by this
version. The parser never resolves an asset URI or executes source content.

Copyright 2026 Lopix Neural Inc. All rights reserved.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
import re
from typing import Any

from keepmorrow.control import checkpoint

from keepmorrow.archive.filesystem import open_regular, safe_directory
from keepmorrow.archive.model import ArchiveError, FileRecord, validate_relative_path
from keepmorrow.formats import check_json_budget

from .model import (
    PROVIDER, ArtifactReference, ConversationRevision, ImportFailure, ImportIssue,
    ImportLimits, MessageNode, ParsedCapture, SourceDocument,
)

_CONVERSATION_FILE = re.compile(r"conversations(?:[-_]?\d+)?\.json\Z")
_DIGEST = re.compile(r"[0-9a-f]{64}\Z")
_TEXT_TYPES = frozenset({"text", "multimodal_text", "code", "execution_output"})


class _MalformedDocument(ValueError):
    pass


class _UnsupportedRecord(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(slots=True)
class _Budget:
    limits: ImportLimits
    conversations: int = 0
    nodes: int = 0
    edges: int = 0
    text_bytes: int = 0
    artifact_references: int = 0
    issues: int = 0

    def charge(self, name: str, amount: int) -> None:
        value = getattr(self, name) + amount
        if value > getattr(self.limits, f"max_{name}"):
            raise ImportFailure(f"Import exceeds the configured {name} limit.")
        setattr(self, name, value)


@dataclass(slots=True)
class _Context:
    source_path: str
    record_index: int
    conversation_key: str
    export_prefix: str
    files: dict[str, FileRecord]
    budget: _Budget
    issues: list[ImportIssue]
    artifacts: list[ArtifactReference] = field(default_factory=list)

    def issue(self, code: str, message: str, node_id: str | None = None) -> None:
        self.budget.charge("issues", 1)
        self.issues.append(ImportIssue(code, self.source_path, self.record_index, node_id, message))


def _identifier(value: object, limits: ImportLimits) -> str:
    if not isinstance(value, str) or not value or not value.strip():
        raise _UnsupportedRecord("invalid_identifier", "A required identifier is absent or malformed.")
    try:
        size = len(value.encode("utf-8"))
    except UnicodeError as error:
        raise _UnsupportedRecord("invalid_identifier", "An identifier contains invalid Unicode.") from error
    if size > limits.max_identifier_bytes or any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise _UnsupportedRecord("invalid_identifier", "An identifier exceeds the supported shape.")
    return value


def _canonical_digest(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True,
                         separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _preflight_json(data: bytes, limits: ImportLimits) -> None:
    """Bound nesting and allocation-driving tokens before JSON constructs objects."""
    try:
        check_json_budget(data, max_bytes=limits.max_json_file_bytes, max_depth=limits.max_json_depth,
                          max_tokens=limits.max_json_tokens)
    except ArchiveError as error:
        raise ImportFailure(str(error)) from error


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _MalformedDocument("The source JSON contains duplicate object keys.")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise _MalformedDocument("The source JSON contains a non-finite number.")


def _decode_json(data: bytes, limits: ImportLimits) -> Any:
    _preflight_json(data, limits)
    try:
        document = json.loads(data.decode("utf-8"), object_pairs_hook=_unique_object,
                              parse_constant=_reject_constant)
        # JSON accepts escaped lone surrogates and exponent overflow by default.
        # Reject both before they reach hashes, output JSON, or rendered views.
        pending = [document]
        while pending:
            checkpoint()
            value = pending.pop()
            if isinstance(value, dict):
                for key, item in value.items():
                    key.encode("utf-8")
                    pending.append(item)
            elif isinstance(value, list):
                pending.extend(value)
            elif isinstance(value, str):
                value.encode("utf-8")
            elif isinstance(value, float) and not math.isfinite(value):
                raise _MalformedDocument("The source JSON contains a non-finite number.")
        return document
    except (UnicodeError, ValueError, RecursionError) as error:
        raise _MalformedDocument("The source document is not supported unambiguous UTF-8 JSON.") from error


def _read_document(root: Path, record: FileRecord, limits: ImportLimits) -> bytes:
    if record.size_bytes > limits.max_json_file_bytes:
        raise ImportFailure("A conversation JSON file exceeds the configured byte limit.")
    path = root / record.path
    try:
        safe_directory(path.parent)
        with open_regular(path) as source:
            before = os.fstat(source.fileno())
            if before.st_size != record.size_bytes:
                raise ImportFailure("A preserved source document no longer matches its inventory.")
            data = source.read(record.size_bytes + 1)
            after = os.fstat(source.fileno())
        if (len(data) != record.size_bytes or before.st_size != after.st_size
                or before.st_mtime_ns != after.st_mtime_ns
                or before.st_ctime_ns != after.st_ctime_ns
                or not os.path.samestat(before, after)
                or hashlib.sha256(data).hexdigest() != record.sha256):
            raise ImportFailure("A preserved source document changed or failed its recorded hash.")
        return data
    except (OSError, ArchiveError) as error:
        if isinstance(error, ImportFailure):
            raise
        raise ImportFailure("A preserved source document could not be read safely.") from error


def _artifact(value: dict[str, Any], node_id: str, location: str,
              kind: str, context: _Context) -> None:
    context.budget.charge("artifact_references", 1)
    source_reference = next((value[key] for key in ("asset_pointer", "url", "id")
                             if isinstance(value.get(key), str)), None)
    original_name = next((value[key] for key in ("name", "file_name")
                          if isinstance(value.get(key), str)), None)
    media_type = next((value[key] for key in ("mime_type", "media_type")
                       if isinstance(value.get(key), str)), None)
    metadata_fields = [source_reference, original_name, media_type]
    for index, (item, maximum) in enumerate(zip(metadata_fields, (8192, 4096, 256))):
        if item is not None and len(item.encode("utf-8")) > maximum:
            metadata_fields[index] = None
            context.issue("oversized_artifact_metadata", "An artifact metadata value remains only in the original record.", node_id)
    source_reference, original_name, media_type = metadata_fields
    relative_path: str | None = None
    stored: FileRecord | None = None
    if "relative_path" in value:
        try:
            relative = validate_relative_path(value["relative_path"])
            relative_path = validate_relative_path(
                f"{context.export_prefix}/{relative}" if context.export_prefix else relative
            )
        except ArchiveError:
            status = "unsupported_reference"
            context.issue("unsafe_artifact_path", "An artifact path is unsafe or unsupported.", node_id)
        else:
            stored = context.files.get(relative_path)
            status = "stored" if stored is not None else "not_supplied"
            if stored is None:
                context.issue("artifact_not_supplied", "A referenced artifact was not supplied.", node_id)
    elif source_reference is not None and source_reference.lower().startswith(("https://", "http://")):
        status = "external_reference"
        context.issue("artifact_external_reference", "An external artifact reference was retained without fetching.", node_id)
    elif source_reference is not None or original_name is not None:
        status = "unresolved"
        context.issue("artifact_unresolved", "An artifact reference has no explicit inventory binding.", node_id)
    else:
        status = "unsupported_reference"
        context.issue("unsupported_artifact_reference", "An artifact reference has an unsupported shape.", node_id)
    context.artifacts.append(ArtifactReference(
        reference_id=_canonical_digest([context.conversation_key, node_id, location]),
        node_id=node_id, kind=kind, source_reference=source_reference,
        original_name=original_name, media_type=media_type,
        relative_path=relative_path, status=status,
        size_bytes=stored.size_bytes if stored else None,
        sha256=stored.sha256 if stored else None,
    ))


def _message(node_id: str, value: object, context: _Context) -> tuple[str | None, str | None, str, str | None]:
    if value is None:
        return None, None, "", None
    if not isinstance(value, dict):
        raise _UnsupportedRecord("invalid_message", "A graph message has an unsupported shape.")
    identifier = value.get("id")
    if identifier is not None:
        identifier = _identifier(identifier, context.budget.limits)
    author = value.get("author")
    role = author.get("role") if isinstance(author, dict) else None
    if not isinstance(role, str) or not role:
        role = None
        context.issue("unsupported_author", "A message author role could not be interpreted.", node_id)
    elif len(role.encode("utf-8")) > context.budget.limits.max_identifier_bytes:
        role = None
        context.issue("unsupported_author", "An oversized message author role remains only in the original record.", node_id)
    content = value.get("content")
    parts: list[str] = []
    content_type: str | None = None
    if not isinstance(content, dict):
        context.issue("unsupported_content", "A message content object could not be interpreted.", node_id)
    else:
        content_type = content.get("content_type")
        if not isinstance(content_type, str) or not content_type:
            content_type = None
        elif len(content_type.encode("utf-8")) > context.budget.limits.max_identifier_bytes:
            content_type = None
        content_parts = content.get("parts")
        if content_type == "image_asset_pointer":
            _artifact(content, node_id, "content", "image", context)
        elif content_type in _TEXT_TYPES and isinstance(content_parts, list):
            for index, part in enumerate(content_parts):
                if isinstance(part, str):
                    context.budget.charge("text_bytes", len(part.encode("utf-8")))
                    parts.append(part)
                elif isinstance(part, dict) and part.get("content_type") == "image_asset_pointer":
                    _artifact(part, node_id, f"content.parts.{index}", "image", context)
                elif (isinstance(part, dict) and part.get("content_type") == "text"
                      and isinstance(part.get("text"), str)):
                    context.budget.charge("text_bytes", len(part["text"].encode("utf-8")))
                    parts.append(part["text"])
                else:
                    context.issue("unsupported_content_part", "A content part remains available only in the original record.", node_id)
        elif content_type in _TEXT_TYPES and isinstance(content.get("text"), str):
            context.budget.charge("text_bytes", len(content["text"].encode("utf-8")))
            parts.append(content["text"])
        else:
            context.issue("unsupported_content", "A message content type remains available only in the original record.", node_id)
    metadata = value.get("metadata")
    if metadata is not None and not isinstance(metadata, dict):
        context.issue("unsupported_message_metadata", "Message metadata has an unsupported shape.", node_id)
    elif isinstance(metadata, dict) and "attachments" in metadata:
        attachments = metadata["attachments"]
        if not isinstance(attachments, list):
            context.issue("unsupported_attachments", "The attachment collection is not an array.", node_id)
        else:
            for index, attachment in enumerate(attachments):
                if isinstance(attachment, dict):
                    _artifact(attachment, node_id, f"metadata.attachments.{index}", "attachment", context)
                else:
                    context.issue("unsupported_attachment", "An attachment record has an unsupported shape.", node_id)
    if len(parts) > 1:
        context.budget.charge("text_bytes", len(parts) - 1)
    return identifier, role, "\n".join(parts), content_type


def _nodes(mapping: object, context: _Context) -> tuple[MessageNode, ...]:
    if not isinstance(mapping, dict):
        raise _UnsupportedRecord("unsupported_mapping", "The conversation has no supported message mapping.")
    context.budget.charge("nodes", len(mapping))
    graph: dict[str, tuple[str | None, tuple[str, ...]]] = {}
    for node_id in sorted(mapping):
        checkpoint()
        value = mapping[node_id]
        _identifier(node_id, context.budget.limits)
        if not isinstance(value, dict) or "parent" not in value or "children" not in value or "message" not in value:
            raise _UnsupportedRecord("invalid_node", "A graph node is missing required structural fields.")
        if "id" in value and value["id"] != node_id:
            raise _UnsupportedRecord("conflicting_node_id", "A graph node identifier conflicts with its mapping key.")
        parent = value["parent"]
        if parent is not None:
            parent = _identifier(parent, context.budget.limits)
        children = value["children"]
        if not isinstance(children, list):
            raise _UnsupportedRecord("invalid_children", "A node's children must be an array of identifiers.")
        context.budget.charge("edges", len(children))
        children_ids = tuple(_identifier(child, context.budget.limits) for child in children)
        if len(set(children_ids)) != len(children_ids):
            raise _UnsupportedRecord("duplicate_edge", "A graph node repeats a child edge.")
        graph[node_id] = parent, children_ids
    for node_id, (parent, children) in graph.items():
        if parent is not None and parent not in graph:
            raise _UnsupportedRecord("dangling_parent", "A graph parent is absent from the supplied mapping.")
        for child in children:
            if child not in graph:
                raise _UnsupportedRecord("dangling_child", "A graph child is absent from the supplied mapping.")
    for node_id, (_, children) in graph.items():
        for child in children:
            if graph[child][0] != node_id:
                raise _UnsupportedRecord("inconsistent_edge", "Parent and child graph declarations disagree.")
    # Count incoming edges once. Repeated parent-child membership scans can turn
    # a broad fan-out into quadratic work; this reconciliation stays O(V + E).
    incoming: dict[str, int] = {node_id: 0 for node_id in graph}
    for _, children in graph.values():
        for child in children:
            incoming[child] += 1
    for node_id, (parent, _) in graph.items():
        if incoming[node_id] != (0 if parent is None else 1):
            raise _UnsupportedRecord("inconsistent_edge", "Parent and child graph declarations disagree.")
    pending = [node_id for node_id, count in incoming.items() if count == 0]
    visited = 0
    while pending:
        checkpoint()
        node_id = pending.pop()
        visited += 1
        for child in graph[node_id][1]:
            incoming[child] -= 1
            if incoming[child] == 0:
                pending.append(child)
    if visited != len(graph):
        raise _UnsupportedRecord("cyclic_graph", "The supplied message graph contains a cycle.")
    result: list[MessageNode] = []
    seen_message_ids: set[str] = set()
    for node_id in graph:
        parent, children = graph[node_id]
        message_id, role, text, content_type = _message(node_id, mapping[node_id]["message"], context)
        if message_id is not None:
            if message_id in seen_message_ids:
                context.issue("duplicate_message_id", "A message identifier occurs at multiple graph nodes.", node_id)
            seen_message_ids.add(message_id)
        result.append(MessageNode(node_id, parent, children, message_id, role, text, content_type))
    return tuple(result)


def _conversation(value: object, source_path: str, record_index: int,
                  account_namespace: str, export_prefix: str, files: dict[str, FileRecord],
                  budget: _Budget, issues: list[ImportIssue]) -> ConversationRevision:
    if not isinstance(value, dict):
        raise _UnsupportedRecord("unsupported_record", "A conversation record must be an object.")
    identifiers = [_identifier(value[key], budget.limits) for key in ("id", "conversation_id")
                   if value.get(key) is not None]
    if not identifiers:
        raise _UnsupportedRecord("missing_conversation_id", "A conversation has no stable source identifier.")
    if len(set(identifiers)) != 1:
        raise _UnsupportedRecord("conflicting_conversation_id", "Conversation identifiers disagree.")
    source_id = identifiers[0]
    conversation_key = _canonical_digest([PROVIDER, account_namespace, source_id])
    context = _Context(source_path, record_index, conversation_key, export_prefix, files, budget, issues)
    title = value.get("title")
    if not isinstance(title, str):
        title = ""
        context.issue("unsupported_title", "A conversation title is absent or unsupported.")
    budget.charge("text_bytes", len(title.encode("utf-8")))
    nodes = _nodes(value.get("mapping"), context)
    current_node_id = value.get("current_node")
    if current_node_id is not None:
        current_node_id = _identifier(current_node_id, budget.limits)
        if current_node_id not in value["mapping"]:
            raise _UnsupportedRecord("missing_current_node", "The current node is absent from the supplied graph.")
    project_id = value.get("project_id")
    association_state, evidence = "association_unknown", "insufficient_source_metadata"
    if project_id is not None:
        try:
            project_id = _identifier(project_id, budget.limits)
        except _UnsupportedRecord:
            project_id = None
            evidence = "unusable_source_field"
            context.issue("unsupported_project_association", "The project identifier could not be interpreted.")
        else:
            association_state, evidence = "project_confirmed", "source_field"
    return ConversationRevision(
        conversation_key=conversation_key, source_id=source_id,
        revision_id=_canonical_digest(value), title=title,
        association_state=association_state, project_id=project_id,
        association_evidence=evidence, current_node_id=current_node_id,
        nodes=nodes, artifacts=tuple(context.artifacts),
        source_path=source_path, record_index=record_index,
    )


def parse_chatgpt_export(
    root: Path,
    files: tuple[FileRecord, ...],
    *,
    account_namespace: str,
    capture_id: str,
    limits: ImportLimits | None = None,
) -> ParsedCapture:
    """Interpret verified source files without changing or fetching any content.

    Recognize conversations.json and numbered variants sharing one directory.
    A wrapper directory is supported; multiple candidate roots are ambiguous.
    Explicit artifact relative paths are rooted at that recognized directory.

    Invalid records remain observable through item-level issues and originals.
    Integrity failures and resource exhaustion raise ImportFailure rather than
    return a truncated successful result. JSON objects use O(document bytes +
    token count) memory; retained normalized records use O(nodes + text + files).
    Graph reconciliation is O(nodes + edges), with canonical ordering and record
    hashing adding sorting and serialized-record costs.
    """
    active = limits or ImportLimits()
    try:
        _identifier(account_namespace, active)
        _identifier(capture_id, active)
    except _UnsupportedRecord as error:
        raise ImportFailure("Account namespace and capture ID must be supported explicit identifiers.") from error
    if len(files) > active.max_files:
        raise ImportFailure("The supplied inventory exceeds the configured file limit.")
    inventory: dict[str, FileRecord] = {}
    folded_paths: set[str] = set()
    for record in files:
        if not isinstance(record, FileRecord):
            raise ImportFailure("Source inventory entries must be FileRecord values.")
        try:
            validate_relative_path(record.path)
        except ArchiveError as error:
            raise ImportFailure("The source inventory contains an unsupported path.") from error
        if (record.path.casefold() in folded_paths or type(record.size_bytes) is not int
                or record.size_bytes < 0 or not isinstance(record.sha256, str)
                or _DIGEST.fullmatch(record.sha256) is None):
            raise ImportFailure("The source inventory is duplicate or malformed.")
        folded_paths.add(record.path.casefold())
        inventory[record.path] = record
    ordered_files = tuple(sorted(files, key=lambda record: record.path))
    candidates = tuple(record for record in ordered_files
                       if _CONVERSATION_FILE.fullmatch(PurePosixPath(record.path).name))
    budget = _Budget(active)
    issues: list[ImportIssue] = []
    documents: list[SourceDocument] = []
    conversations: list[ConversationRevision] = []
    if not candidates:
        issues.append(ImportIssue("no_supported_documents", None, None, None,
                                  "No supported conversation JSON filenames were supplied."))
        return ParsedCapture(account_namespace, capture_id, "unsupported", (), (), ordered_files, tuple(issues))
    roots = {str(PurePosixPath(record.path).parent) for record in candidates}
    if len(roots) != 1:
        issues.append(ImportIssue("ambiguous_export_roots", None, None, None,
                                  "Conversation JSON files occur in multiple possible export roots."))
        documents = [SourceDocument(item.path, item.sha256, item.size_bytes, "unsupported", None, 0, 0)
                     for item in candidates]
        return ParsedCapture(account_namespace, capture_id, "unsupported", tuple(documents), (), ordered_files, tuple(issues))
    export_prefix = next(iter(roots))
    if export_prefix == ".":
        export_prefix = ""
    if sum(item.size_bytes for item in candidates) > active.max_json_total_bytes:
        raise ImportFailure("Conversation JSON files exceed the configured aggregate byte limit.")
    try:
        preserved_root = safe_directory(root)
    except (OSError, ArchiveError) as error:
        raise ImportFailure("The preserved source root is not a supported ordinary directory.") from error
    seen_revisions: dict[str, set[str]] = {}
    for candidate in candidates:
        checkpoint()
        try:
            document = _decode_json(_read_document(preserved_root, candidate, active), active)
        except _MalformedDocument:
            budget.charge("issues", 1)
            issues.append(ImportIssue("malformed_json", candidate.path, None, None,
                                      "The source document is not supported unambiguous UTF-8 JSON."))
            documents.append(SourceDocument(candidate.path, candidate.sha256, candidate.size_bytes,
                                            "malformed", None, 0, 0))
            continue
        if not isinstance(document, list):
            budget.charge("issues", 1)
            issues.append(ImportIssue("unsupported_document", candidate.path, None, None,
                                      "A conversation source document must contain a JSON array."))
            documents.append(SourceDocument(candidate.path, candidate.sha256, candidate.size_bytes,
                                            "unsupported", None, 0, 0))
            continue
        budget.charge("conversations", len(document))
        accepted = rejected = 0
        for index, record in enumerate(document):
            checkpoint()
            try:
                parsed = _conversation(record, candidate.path, index, account_namespace,
                                       export_prefix, inventory, budget, issues)
            except _UnsupportedRecord as error:
                budget.charge("issues", 1)
                issues.append(ImportIssue(error.code, candidate.path, index, None, str(error)))
                rejected += 1
                continue
            prior = seen_revisions.setdefault(parsed.conversation_key, set())
            if prior:
                budget.charge("issues", 1)
                duplicate = parsed.revision_id in prior
                issues.append(ImportIssue(
                    "duplicate_record_occurrence" if duplicate else "multiple_revisions_in_capture",
                    candidate.path, index, None,
                    "A repeated conversation occurrence was retained without choosing a winner.",
                ))
            prior.add(parsed.revision_id)
            conversations.append(parsed)
            accepted += 1
        documents.append(SourceDocument(candidate.path, candidate.sha256, candidate.size_bytes,
                                        "parsed", len(document), accepted, rejected))
        # Release each decoded source tree before reading the next numbered file.
        del document
    status = "partial" if issues else "complete"
    if documents and all(document.status == "unsupported" for document in documents):
        status = "unsupported"
    return ParsedCapture(account_namespace, capture_id, status, tuple(documents),
                         tuple(conversations), ordered_files, tuple(issues))
