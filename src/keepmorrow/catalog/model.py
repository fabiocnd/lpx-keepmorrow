"""Versioned collection contracts and validation at the persisted-data boundary.

Original files remain authoritative. A catalog is a deterministic derivative,
and its hashes establish consistency rather than publisher authentication.
Copyright 2026 Lopix Neural Inc. All rights reserved.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass, fields
from typing import Any

from ..archive.model import ArchiveError, FileRecord, Manifest, validate_relative_path
from ..formats import check_json_budget

COLLECTION_FORMAT = "lpx-keepmorrow.collection"
COLLECTION_VERSION = 1
PROVIDER = "openai.chatgpt"
CATALOG_PATH = "catalog.json"
REPORT_PATH = "report.json"
VIEW_PATH = "index.html"
ASSOCIATION_STATES = frozenset({"project_confirmed", "standalone_confirmed", "association_unknown"})
_DIGEST = re.compile(r"[0-9a-f]{64}\Z")
_STORAGE_ID = re.compile(r"[0-9]{6}\Z")
Document = dict[str, Any]


class CatalogError(ArchiveError):
    """A collection cannot satisfy the declared semantic or resource contract."""


@dataclass(frozen=True, slots=True)
class CatalogLimits:
    """Bounds include derived metadata; binary payload limits are independent."""

    max_captures: int = 64
    max_catalog_bytes: int = 64 * 1024**2
    max_conversations: int = 10_000
    max_revisions: int = 20_000
    max_occurrences: int = 40_000
    max_nodes: int = 200_000
    max_artifacts: int = 100_000
    max_text_bytes: int = 64 * 1024**2
    max_decisions: int = 10_000
    max_query_characters: int = 1_024
    max_results: int = 200
    max_response_bytes: int = 1024**2
    max_json_depth: int = 64
    max_json_tokens: int = 2_000_000

    def __post_init__(self) -> None:
        for field in fields(self):
            if type(getattr(self, field.name)) is not int or getattr(self, field.name) <= 0:
                raise CatalogError(f"{field.name} must be a positive integer.")


def json_bytes(document: object) -> bytes:
    """Use one stable representation for persisted derivatives and identity inputs."""
    try:
        return (json.dumps(document, ensure_ascii=False, sort_keys=True,
                           separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")
    except (UnicodeError, ValueError, TypeError, RecursionError) as error:
        raise CatalogError("The catalog contains unsupported JSON values.") from error


def content_digest(document: object) -> str:
    return hashlib.sha256(json_bytes(document)).hexdigest()


def encoded_size(document: object, maximum: int) -> int:
    """Charge retained metadata before a complete serialized copy is allocated."""
    size = 1
    encoder = json.JSONEncoder(ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    try:
        for part in encoder.iterencode(document):
            size += len(part.encode("utf-8"))
            if size > maximum:
                raise CatalogError("The retained catalog metadata exceeds its byte budget.")
    except CatalogError:
        raise
    except (ValueError, TypeError, UnicodeError, RecursionError) as error:
        raise CatalogError("The catalog contains unsupported JSON values.") from error
    return size


def validate_namespace(value: object) -> str:
    namespace = _text(value, "account namespace", 256)
    if not namespace.strip() or any(ord(character) < 32 for character in namespace):
        raise CatalogError("The account namespace must be a nonempty, printable local label.")
    return namespace


def _text(value: object, label: str, maximum: int = 4096, *, empty: bool = False) -> str:
    if not isinstance(value, str) or (not empty and not value):
        raise CatalogError(f"The {label} must be a supported string.")
    try:
        length = len(value.encode("utf-8"))
    except UnicodeError as error:
        raise CatalogError(f"The {label} contains invalid Unicode.") from error
    if length > maximum:
        raise CatalogError(f"The {label} exceeds its byte limit.")
    return value


def _digest(value: object, label: str) -> str:
    if not isinstance(value, str) or _DIGEST.fullmatch(value) is None:
        raise CatalogError(f"The {label} is not a lowercase SHA-256 digest.")
    return value


def _object(value: object, label: str) -> Document:
    if not isinstance(value, dict):
        raise CatalogError(f"The {label} must be an object.")
    return value


def _array(value: object, label: str, maximum: int) -> list[Any]:
    if not isinstance(value, list) or len(value) > maximum:
        raise CatalogError(f"The {label} must be an array within its configured limit.")
    return value


def _enum(value: object, allowed: set[str] | frozenset[str], label: str) -> str:
    if not isinstance(value, str) or value not in allowed:
        raise CatalogError(f"The {label} is unsupported.")
    return value


def parse_collection(data: bytes, manifest: Manifest, limits: CatalogLimits) -> Document:
    """Validate an untrusted derivative against the verified payload inventory."""
    if len(data) > limits.max_catalog_bytes:
        raise CatalogError("The collection catalog exceeds its byte limit.")
    try:
        check_json_budget(data, max_bytes=limits.max_catalog_bytes, max_depth=limits.max_json_depth,
                          max_tokens=limits.max_json_tokens)
    except ArchiveError as error:
        raise CatalogError(str(error)) from error

    def unique_object(pairs: list[tuple[str, Any]]) -> Document:
        result: Document = {}
        for key, value in pairs:
            if key in result:
                raise CatalogError("The catalog contains duplicate JSON keys.")
            result[key] = value
        return result

    def reject_constant(value: str) -> None:
        raise CatalogError("The catalog contains a non-finite JSON number.")

    def finite_float(value: str) -> float:
        result = float(value)
        if not math.isfinite(result):
            raise CatalogError("The catalog contains a non-finite JSON number.")
        return result

    try:
        document = json.loads(data.decode("utf-8"), object_pairs_hook=unique_object,
                              parse_constant=reject_constant, parse_float=finite_float)
        pending = [document]
        while pending:
            value = pending.pop()
            if isinstance(value, dict):
                for key, item in value.items():
                    key.encode("utf-8")
                    pending.append(item)
            elif isinstance(value, list):
                pending.extend(value)
            elif isinstance(value, str):
                value.encode("utf-8")
    except CatalogError:
        raise
    except (ValueError, UnicodeError, RecursionError) as error:
        raise CatalogError("The collection is not supported UTF-8 JSON.") from error
    validate_collection(document, manifest, limits)
    return document


def validate_association(value: object) -> Document:
    association = _object(value, "association")
    state = association.get("state")
    if not isinstance(state, str) or state not in ASSOCIATION_STATES:
        raise CatalogError("The association state is unsupported.")
    project_id = association.get("project_id")
    if state == "project_confirmed":
        _text(project_id, "project identifier")
    elif project_id is not None:
        raise CatalogError("Only confirmed project associations may name a project.")
    _object(association.get("evidence"), "association evidence")
    return association


def validate_collection(document: object, manifest: Manifest, limits: CatalogLimits) -> None:
    """Check identity, graph topology, provenance, and exact artifact bindings.

    Lookup tables make validation linear in nodes, edges, files, and occurrences.
    The input-byte ceiling bounds JSON parsing before these semantic checks.
    """
    root = _object(document, "collection")
    if (root.get("format") != COLLECTION_FORMAT or type(root.get("version")) is not int
            or root["version"] != COLLECTION_VERSION or root.get("provider") != PROVIDER):
        raise CatalogError("The collection format, version, provider, or scope is unsupported.")
    _enum(root.get("scope"), {"supplied_exports", "selected_conversations"}, "collection scope")
    validate_namespace(root.get("account_namespace"))
    if root.get("parser_compatibility") != "experimental":
        raise CatalogError("The collection parser compatibility claim is unsupported.")
    captures = _array(root.get("captures"), "captures", limits.max_captures)
    conversations = _array(root.get("conversations"), "conversations", limits.max_conversations)
    manifest_files = {item.path: item for item in manifest.files}
    capture_lookup: dict[str, Document] = {}
    file_lookup: dict[tuple[str, str], FileRecord] = {}
    storage_ids: set[str] = set()
    expected_paths = {CATALOG_PATH, REPORT_PATH, VIEW_PATH}
    for value in captures:
        capture = _object(value, "capture")
        capture_id = _digest(capture.get("capture_id"), "capture identifier")
        storage_id = capture.get("storage_id")
        if (capture_id in capture_lookup or not isinstance(storage_id, str)
                or _STORAGE_ID.fullmatch(storage_id) is None or storage_id in storage_ids):
            raise CatalogError("The capture identifiers are duplicate or unsupported.")
        capture_lookup[capture_id] = capture
        storage_ids.add(storage_id)
        _enum(capture.get("source_kind"), {"directory", "zip", "selection"}, "capture source kind")
        if (root["scope"] == "selected_conversations") != (capture["source_kind"] == "selection"):
            raise CatalogError("The capture source kind does not match its collection scope.")
        _digest(capture.get("source_fingerprint"), "source fingerprint")
        files = _array(capture.get("files"), "capture files", len(manifest.files))
        for file_value in files:
            item = _object(file_value, "capture file")
            relative = validate_relative_path(item.get("path"))
            path = f"captures/{storage_id}/source/{relative}"
            record = FileRecord(relative, item.get("size_bytes"), item.get("sha256"))
            expected = manifest_files.get(path)
            if (type(record.size_bytes) is not int or expected is None or expected.size_bytes != record.size_bytes
                    or expected.sha256 != record.sha256 or (capture_id, relative) in file_lookup):
                raise CatalogError("A capture file does not match the verified payload inventory.")
            file_lookup[capture_id, relative] = record
            expected_paths.add(path)
        original_zip = capture.get("original_zip")
        if original_zip is not None:
            if root["scope"] == "selected_conversations":
                raise CatalogError("Selected packages must not contain whole original ZIP containers.")
            item = _object(original_zip, "original ZIP")
            path = f"captures/{storage_id}/original.zip"
            expected = manifest_files.get(path)
            if type(item.get("size_bytes")) is not int or expected is None or item != expected.as_dict():
                raise CatalogError("The original ZIP does not match the verified payload inventory.")
            expected_paths.add(path)
        if capture["source_kind"] == "zip" and original_zip is None:
            raise CatalogError("A ZIP capture must retain its complete original container.")
        _enum(capture.get("status"), {"complete", "partial", "unsupported"}, "capture parser status")
        parser = _object(capture.get("parser"), "capture parser")
        if (parser.get("name") != "chatgpt-mapping" or type(parser.get("version")) is not int
                or parser["version"] != 1 or parser.get("compatibility") != "experimental"):
            raise CatalogError("The capture parser profile is unsupported.")
        _object(capture.get("summary"), "capture summary")
        _array(capture.get("issues"), "capture issues", 100_000)
        source_documents = _array(capture.get("source_documents"), "source documents", len(files))
        source_paths: set[str] = set()
        for source_value in source_documents:
            source_document = _object(source_value, "source document")
            source_path = validate_relative_path(source_document.get("path"))
            supplied = file_lookup.get((capture_id, source_path))
            if (source_path in source_paths or supplied is None
                    or type(source_document.get("size_bytes")) is not int
                    or source_document["size_bytes"] != supplied.size_bytes
                    or source_document.get("sha256") != supplied.sha256):
                raise CatalogError("Source document metadata does not match its preserved file.")
            source_paths.add(source_path)
            state = _enum(source_document.get("status"), {"parsed", "malformed", "unsupported"}, "source document status")
            count = source_document.get("record_count")
            accepted = source_document.get("accepted_records")
            rejected = source_document.get("rejected_records")
            if (type(accepted) is not int or accepted < 0 or type(rejected) is not int or rejected < 0
                    or (state == "parsed" and (type(count) is not int or count < 0 or accepted + rejected != count))
                    or (state != "parsed" and (count is not None or accepted != 0 or rejected != 0))):
                raise CatalogError("Source document record counts are inconsistent.")
    if expected_paths != set(manifest_files):
        raise CatalogError("The collection catalog does not cover the archive file inventory.")

    source_documents_by_capture = {
        item["capture_id"]: {source["path"]: source for source in item["source_documents"]}
        for item in captures
    }
    keys: set[str] = set()
    node_count = revision_count = occurrence_count = artifact_count = text_bytes = 0
    for value in conversations:
        conversation = _object(value, "conversation")
        key = _digest(conversation.get("conversation_key"), "conversation key")
        source_id = _text(conversation.get("source_id"), "source conversation identifier")
        identity = json.dumps([PROVIDER, root["account_namespace"], source_id], ensure_ascii=False,
                              separators=(",", ":"), sort_keys=True).encode("utf-8")
        if hashlib.sha256(identity).hexdigest() != key:
            raise CatalogError("The conversation key does not match its namespaced source identity.")
        if key in keys:
            raise CatalogError("The catalog contains duplicate logical conversations.")
        keys.add(key)
        revisions = _array(conversation.get("revisions"), "revisions", limits.max_revisions)
        if not revisions:
            raise CatalogError("A cataloged conversation must contain a revision.")
        revision_ids: set[str] = set()
        for revision_value in revisions:
            revision = _object(revision_value, "revision")
            revision_id = _digest(revision.get("revision_id"), "revision identifier")
            if revision_id in revision_ids:
                raise CatalogError("A conversation contains duplicate revisions.")
            revision_ids.add(revision_id)
            revision_count += 1
            title = _text(revision.get("title"), "conversation title", limits.max_text_bytes, empty=True)
            text_bytes += len(title.encode("utf-8"))
            validate_association(revision.get("association"))
            nodes = _array(revision.get("nodes"), "message nodes", limits.max_nodes)
            node_count += len(nodes)
            by_node: dict[str, Document] = {}
            child_sets: dict[str, set[str]] = {}
            for node_value in nodes:
                node = _object(node_value, "message node")
                identifier = _text(node.get("id"), "message node identifier")
                if identifier in by_node:
                    raise CatalogError("A revision contains duplicate message nodes.")
                by_node[identifier] = node
                if "parent_id" not in node:
                    raise CatalogError("A message node must declare its parent, including a null root.")
                text = _text(node.get("text"), "message text", limits.max_text_bytes, empty=True)
                text_bytes += len(text.encode("utf-8"))
                for field in ("message_id", "role", "content_type", "parent_id"):
                    if node.get(field) is not None:
                        _text(node[field], f"node {field}")
                children = _array(node.get("children_ids"), "child nodes", limits.max_nodes)
                if any(not isinstance(child, str) for child in children) or len(set(children)) != len(children):
                    raise CatalogError("Message child references must be unique strings.")
                child_sets[identifier] = set(children)
            roots: list[str] = []
            for identifier, node in by_node.items():
                parent = node["parent_id"]
                if parent is None:
                    roots.append(identifier)
                elif parent not in by_node or identifier not in child_sets[parent]:
                    raise CatalogError("Message parent and child references disagree.")
                for child in node["children_ids"]:
                    if child not in by_node or by_node[child]["parent_id"] != identifier:
                        raise CatalogError("Message child and parent references disagree.")
            visited: set[str] = set()
            pending = roots[:]
            while pending:
                identifier = pending.pop()
                if identifier in visited:
                    raise CatalogError("The message graph contains a cycle or repeated edge.")
                visited.add(identifier)
                pending.extend(by_node[identifier]["children_ids"])
            if len(visited) != len(by_node):
                raise CatalogError("The message graph contains an unreachable cycle.")
            current = revision.get("current_node_id")
            if current is not None and (not isinstance(current, str) or current not in by_node):
                raise CatalogError("The current message node is absent from its revision.")
            occurrences = _array(revision.get("occurrences"), "revision occurrences", limits.max_occurrences)
            if not occurrences:
                raise CatalogError("A revision must retain source provenance.")
            occurrence_count += len(occurrences)
            for occurrence_value in occurrences:
                occurrence = _object(occurrence_value, "revision occurrence")
                capture_id = occurrence.get("capture_id")
                if not isinstance(capture_id, str) or capture_id not in capture_lookup:
                    raise CatalogError("An occurrence references an unknown capture.")
                provenance = _object(occurrence.get("provenance"), "record provenance")
                source_path = validate_relative_path(provenance.get("source_path"))
                if root["scope"] == "supplied_exports" and (capture_id, source_path) not in file_lookup:
                    raise CatalogError("An occurrence references an unpreserved source document.")
                if (type(provenance.get("record_index")) is not int or provenance["record_index"] < 0
                        or provenance.get("record_sha256") != revision_id):
                    raise CatalogError("The record provenance does not match its revision.")
                if root["scope"] == "supplied_exports":
                    source_document = source_documents_by_capture[capture_id].get(source_path)
                    if (source_document is None or source_document["status"] != "parsed"
                            or provenance["record_index"] >= source_document["record_count"]):
                        raise CatalogError("An occurrence does not bind to a parsed source record.")
                artifacts = _array(occurrence.get("artifacts"), "artifact references", limits.max_artifacts)
                artifact_count += len(artifacts)
                for artifact_value in artifacts:
                    artifact = _object(artifact_value, "artifact reference")
                    _text(artifact.get("reference_id"), "artifact reference identifier")
                    status = artifact.get("status")
                    _enum(status, {"stored", "not_supplied", "unresolved", "external_reference", "unsupported_reference", "excluded_by_selection"},
                          "artifact availability state")
                    if not isinstance(artifact.get("node_id"), str) or artifact["node_id"] not in by_node:
                        raise CatalogError("An artifact references an unknown message node.")
                    relative = artifact.get("relative_path")
                    if relative is not None:
                        validate_relative_path(relative)
                    if status == "stored":
                        record = file_lookup.get((capture_id, relative))
                        if (type(artifact.get("size_bytes")) is not int or record is None or artifact.get("sha256") != record.sha256
                                or artifact.get("size_bytes") != record.size_bytes):
                            raise CatalogError("A stored artifact does not match its captured file.")
            if (revision_count > limits.max_revisions or node_count > limits.max_nodes
                    or occurrence_count > limits.max_occurrences or artifact_count > limits.max_artifacts
                    or text_bytes > limits.max_text_bytes):
                raise CatalogError("The collection exceeds its semantic resource limits.")

    decisions = _array(root.get("association_history"), "association decisions", limits.max_decisions)
    previous: str | None = None
    for sequence, decision_value in enumerate(decisions, 1):
        decision = _object(decision_value, "association decision")
        key = decision.get("conversation_key")
        if not isinstance(key, str) or key not in keys:
            raise CatalogError("An association decision references an unknown conversation.")
        validate_association(decision.get("association"))
        _text(decision.get("reason"), "association decision reason", 2048)
        if type(decision.get("sequence")) is not int or decision["sequence"] != sequence or decision.get("previous_decision_id") != previous:
            raise CatalogError("The association decision history is not contiguous.")
        unsigned = {name: value for name, value in decision.items() if name != "decision_id"}
        previous = _digest(decision.get("decision_id"), "association decision identifier")
        if content_digest(unsigned) != previous:
            raise CatalogError("An association decision does not match its recorded content.")
    summary = _object(root.get("summary"), "collection summary")
    expected_summary = collection_summary(root)
    if (summary != expected_summary or set(summary) != set(expected_summary)
            or any(type(value) is not int for value in summary.values())):
        raise CatalogError("The collection summary does not match its validated records.")


def collection_summary(document: Document) -> Document:
    counts: Document = {
        "capture_count": len(document["captures"]),
        "unique_source_count": len({item["source_fingerprint"] for item in document["captures"]}),
        "conversation_count": len(document["conversations"]),
        "revision_count": 0, "occurrence_count": 0, "message_node_count": 0,
        "branched_revision_count": 0, "stored_artifact_references": 0,
        "unavailable_artifact_references": 0,
        "source_file_count": sum(len(item["files"]) for item in document["captures"]),
        "source_bytes": sum(file["size_bytes"] for item in document["captures"] for file in item["files"]),
        "partial_capture_count": sum(item["status"] != "complete" for item in document["captures"]),
        "association_decision_count": len(document["association_history"]),
    }
    for conversation in document["conversations"]:
        for revision in conversation["revisions"]:
            counts["revision_count"] += 1
            counts["message_node_count"] += len(revision["nodes"])
            counts["branched_revision_count"] += any(len(node["children_ids"]) > 1 for node in revision["nodes"])
            counts["occurrence_count"] += len(revision["occurrences"])
            for occurrence in revision["occurrences"]:
                for artifact in occurrence["artifacts"]:
                    field = "stored_artifact_references" if artifact["status"] == "stored" else "unavailable_artifact_references"
                    counts[field] += 1
    return counts


def effective_associations(document: Document) -> dict[str, Document]:
    """Use the most recently supplied occurrence, then explicit operator decisions."""
    positions = {capture["capture_id"]: index for index, capture in enumerate(document["captures"])}
    result: dict[str, Document] = {}
    for conversation in document["conversations"]:
        revision = max(conversation["revisions"], key=lambda item: max(
            (positions[occurrence["capture_id"]], occurrence["provenance"]["record_index"])
            for occurrence in item["occurrences"]))
        result[conversation["conversation_key"]] = revision["association"]
    for decision in document["association_history"]:
        result[decision["conversation_key"]] = decision["association"]
    return result
