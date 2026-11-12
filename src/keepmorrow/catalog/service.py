"""Immutable collection generations, explicit associations, and selected recovery.

The application preserves input bytes before interpretation. Each new generation
has an independent ordinary archive manifest; previous generations stay intact.
Copyright 2026 Lopix Neural Inc. All rights reserved.
"""

from __future__ import annotations

import copy
import hashlib
import os
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

from ..archive import Limits, load_manifest, verify_archive
from ..archive.assembly import ArchiveAssembly, assembling_archive
from ..archive.filesystem import destination_path, open_regular, safe_directory
from ..archive.model import FileRecord, Manifest, PAYLOAD_NAME
from ..importers import ImportLimits, parse_chatgpt_export
from ..importers.zip_intake import prepared_export
from ..formats import check_json_budget
from .model import (
    CATALOG_PATH, COLLECTION_FORMAT, COLLECTION_VERSION, PROVIDER, REPORT_PATH,
    VIEW_PATH, CatalogError, CatalogLimits, Document, collection_summary,
    content_digest, effective_associations, encoded_size, json_bytes, parse_collection,
    validate_association, validate_collection, validate_namespace,
)
from .views import render_collection


@dataclass(frozen=True, slots=True)
class CollectionResult:
    """Separate byte verification from the parser's coverage of supplied records."""

    manifest: Manifest
    summary: Document
    semantic_status: str

    def as_dict(self) -> Document:
        return {
            "stage": "collection_validation", "verified": True,
            "scope": "explicitly_supplied_material", "account_completeness": "not_asserted",
            "parser_compatibility": "experimental", "semantic_status": self.semantic_status,
            "file_count": len(self.manifest.files),
            "total_bytes": sum(item.size_bytes for item in self.manifest.files),
            "summary": self.summary,
        }


@dataclass(frozen=True, slots=True)
class LoadedCollection:
    root: Path
    manifest: Manifest
    document: Document


def _read_catalog(payload: Path, record: FileRecord, maximum: int) -> bytes:
    if record.size_bytes > maximum:
        raise CatalogError("The collection catalog exceeds its byte limit.")
    with open_regular(payload / record.path) as source:
        before = os.fstat(source.fileno())
        if before.st_size != record.size_bytes:
            raise CatalogError("The catalog changed after verification.")
        data = source.read(record.size_bytes + 1)
        after = os.fstat(source.fileno())
        if (len(data) != record.size_bytes or before.st_size != after.st_size
                or before.st_mtime_ns != after.st_mtime_ns or before.st_ctime_ns != after.st_ctime_ns
                or hashlib.sha256(data).hexdigest() != record.sha256):
            raise CatalogError("The catalog changed while being read.")
    return data


def load_collection(
    archive: Path, *, limits: Limits | None = None, catalog_limits: CatalogLimits | None = None,
) -> LoadedCollection:
    """Verify all supplied archive bytes before trusting a persisted catalog.

    Queries deliberately pay this O(B) integrity cost. A future authenticated
    index cache needs a separate invalidation and trust contract.
    """
    active_limits = limits or Limits()
    semantic_limits = catalog_limits or CatalogLimits()
    root = safe_directory(archive)
    manifest = load_manifest(root, limits=active_limits)
    if not verify_archive(root, limits=active_limits).verified:
        raise CatalogError("The collection failed archive verification.")
    if load_manifest(root, limits=active_limits) != manifest:
        raise CatalogError("The collection manifest changed during verification.")
    record = next((item for item in manifest.files if item.path == CATALOG_PATH), None)
    if record is None:
        raise CatalogError("The archive does not contain a supported collection catalog.")
    data = _read_catalog(root / PAYLOAD_NAME, record, semantic_limits.max_catalog_bytes)
    return LoadedCollection(root, manifest, parse_collection(data, manifest, semantic_limits))


def _new_collection(namespace: str) -> Document:
    return {
        "format": COLLECTION_FORMAT, "version": COLLECTION_VERSION,
        "provider": PROVIDER, "account_namespace": namespace,
        "scope": "supplied_exports", "parser_compatibility": "experimental",
        "captures": [], "conversations": [], "association_history": [],
    }


class _RevisionIndex:
    """Reconcile source identities with hash maps; titles never participate."""

    def __init__(self, document: Document, limits: CatalogLimits) -> None:
        self.document = document
        self.limits = limits
        self.conversations = {item["conversation_key"]: item for item in document["conversations"]}
        self.revisions = {(item["conversation_key"], revision["revision_id"]): revision
                          for item in document["conversations"] for revision in item["revisions"]}
        self.nodes = self.text_bytes = self.occurrences = self.artifacts = 0
        for revision in self.revisions.values():
            self.nodes += len(revision["nodes"])
            self.text_bytes += len(revision["title"].encode("utf-8"))
            self.text_bytes += sum(len(node["text"].encode("utf-8")) for node in revision["nodes"])
            self.occurrences += len(revision["occurrences"])
            self.artifacts += sum(len(item["artifacts"]) for item in revision["occurrences"])
        self.metadata_bytes = encoded_size(document, limits.max_catalog_bytes)

    def charge_metadata(self, value: object) -> None:
        # The extra delimiter allowance is deliberately conservative. Source
        # record hashes are still based on their separately defined canonical
        # representation, independent of this allocation budget.
        self.metadata_bytes += encoded_size(value, self.limits.max_catalog_bytes) + 16
        if self.metadata_bytes > self.limits.max_catalog_bytes:
            raise CatalogError("The retained catalog metadata exceeds its byte budget.")

    def add(self, capture: Document) -> None:
        for source in capture["conversations"]:
            key = source["conversation_key"]
            conversation = self.conversations.get(key)
            if conversation is None:
                conversation = {"conversation_key": key, "source_id": source["source_id"], "revisions": []}
                self.charge_metadata(conversation)
                self.document["conversations"].append(conversation)
                self.conversations[key] = conversation
            elif conversation["source_id"] != source["source_id"]:
                raise CatalogError("Distinct source identities produced a conflicting conversation key.")
            revision_key = (key, source["revision_id"])
            revision = self.revisions.get(revision_key)
            if revision is None:
                revision = {name: source[name] for name in
                            ("revision_id", "title", "association", "current_node_id", "nodes")}
                revision["occurrences"] = []
                self.charge_metadata(revision)
                conversation["revisions"].append(revision)
                self.revisions[revision_key] = revision
                self.nodes += len(revision["nodes"])
                self.text_bytes += len(revision["title"].encode("utf-8"))
                self.text_bytes += sum(len(node["text"].encode("utf-8")) for node in revision["nodes"])
            occurrence = {
                "capture_id": capture["capture_id"], "provenance": source["provenance"],
                "artifacts": source["artifacts"],
            }
            self.charge_metadata(occurrence)
            revision["occurrences"].append(occurrence)
            self.occurrences += 1
            self.artifacts += len(source["artifacts"])
            if (len(self.conversations) > self.limits.max_conversations
                    or len(self.revisions) > self.limits.max_revisions
                    or self.nodes > self.limits.max_nodes or self.text_bytes > self.limits.max_text_bytes
                    or self.occurrences > self.limits.max_occurrences or self.artifacts > self.limits.max_artifacts):
                raise CatalogError("The collection exceeds its semantic resource limits.")


def _source_manifests(collection: LoadedCollection) -> dict[str, Manifest]:
    """Partition the previous verified inventory in one pass over its entries."""
    ids = {item["storage_id"] for item in collection.document["captures"]}
    directories: dict[str, list[str]] = {identifier: [] for identifier in ids}
    files: dict[str, list[FileRecord]] = {identifier: [] for identifier in ids}
    for directory in collection.manifest.directories:
        parts = directory.split("/", 3)
        if len(parts) == 4 and parts[0] == "captures" and parts[1] in ids and parts[2] == "source":
            directories[parts[1]].append(parts[3])
    for item in collection.manifest.files:
        parts = item.path.split("/", 3)
        if len(parts) == 4 and parts[0] == "captures" and parts[1] in ids and parts[2] == "source":
            files[parts[1]].append(FileRecord(parts[3], item.size_bytes, item.sha256))
    return {identifier: Manifest(tuple(directories[identifier]), tuple(files[identifier])) for identifier in ids}


def _copy_captures(collection: LoadedCollection, assembly: ArchiveAssembly) -> None:
    manifests = _source_manifests(collection)
    payload = collection.root / PAYLOAD_NAME
    for capture in collection.document["captures"]:
        prefix = f"captures/{capture['storage_id']}/source"
        observed = assembly.add_tree(payload / prefix, prefix)
        if observed != manifests[capture["storage_id"]]:
            raise CatalogError("A previous capture changed after verification.")
        if capture["original_zip"] is not None:
            path = f"captures/{capture['storage_id']}/original.zip"
            observed_zip = assembly.add_file(payload / path, path)
            if observed_zip.as_dict() != capture["original_zip"]:
                raise CatalogError("A previous original ZIP changed after verification.")


def _record_capture(
    document: Document, assembly: ArchiveAssembly, source: Path,
    index: _RevisionIndex, archive_limits: Limits, import_limits: ImportLimits,
) -> None:
    ordinal = len(document["captures"]) + 1
    if ordinal > index.limits.max_captures:
        raise CatalogError("The collection exceeds its capture limit.")
    storage_id = f"{ordinal:06d}"
    prefix = f"captures/{storage_id}/source"
    # Exit intake before archive publication. Its final source checks must be
    # able to cancel the entire generation, including a changed original ZIP.
    with prepared_export(source, limits=archive_limits) as prepared:
        manifest = assembly.add_tree(prepared.directory, prefix)
        original_zip = None
        if prepared.original_zip is not None:
            original_zip = assembly.add_file(prepared.original_zip, f"captures/{storage_id}/original.zip").as_dict()
        fingerprint = content_digest({
            "source_manifest_sha256": hashlib.sha256(manifest.to_bytes()).hexdigest(),
            "original_zip_sha256": original_zip["sha256"] if original_zip else None,
        })
        capture_id = content_digest([document["account_namespace"], fingerprint, ordinal])
        parsed = parse_chatgpt_export(
            assembly.payload / prefix, manifest.files,
            account_namespace=document["account_namespace"], capture_id=capture_id, limits=import_limits,
        ).as_dict()
        capture = {name: parsed[name] for name in
                   ("capture_id", "parser", "status", "source_documents", "files", "issues", "summary")}
        capture.update({"storage_id": storage_id, "source_kind": "zip" if original_zip else "directory",
                        "source_fingerprint": fingerprint, "original_zip": original_zip})
        index.charge_metadata(capture)
        document["captures"].append(capture)
        index.add(parsed)


def _write_derivatives(assembly: ArchiveAssembly, document: Document, limits: CatalogLimits) -> Document:
    document["conversations"].sort(key=lambda item: item["conversation_key"])
    summary = collection_summary(document)
    document["summary"] = summary
    data = json_bytes(document)
    if len(data) > limits.max_catalog_bytes:
        raise CatalogError("The derived catalog exceeds its configured byte limit.")
    check_json_budget(data, max_bytes=limits.max_catalog_bytes, max_depth=limits.max_json_depth,
                      max_tokens=limits.max_json_tokens)
    records = [assembly.add_bytes(CATALOG_PATH, data)]
    report = {
        "format": "lpx-keepmorrow.coverage-report", "version": 1,
        "scope": document["scope"], "account_completeness": "not_asserted",
        "parser_compatibility": "experimental", "summary": summary,
        "captures": [{name: capture[name] for name in
                      ("capture_id", "status", "source_documents", "issues", "summary")}
                     for capture in document["captures"]],
    }
    records.append(assembly.add_bytes(REPORT_PATH, json_bytes(report)))
    view = render_collection(document)
    if len(view) > limits.max_catalog_bytes * 4:
        raise CatalogError("The derived readable view exceeds its configured byte limit.")
    records.append(assembly.add_bytes(VIEW_PATH, view))
    for capture in document["captures"]:
        prefix = f"captures/{capture['storage_id']}/source"
        records.extend(FileRecord(f"{prefix}/{item['path']}", item["size_bytes"], item["sha256"])
                       for item in capture["files"])
        if capture["original_zip"] is not None:
            records.append(FileRecord(**capture["original_zip"]))
    # This is a semantic inventory check over the copy-time records. The
    # assembly independently rereads payload bytes before publication.
    validate_collection(document, Manifest((), tuple(records)), limits)
    return summary


def _finish(assembly: ArchiveAssembly, document: Document, summary: Document) -> CollectionResult:
    if assembly.manifest is None:
        raise CatalogError("The collection was not published.")
    statuses = {item["status"] for item in document["captures"]}
    semantic_status = "complete" if statuses == {"complete"} else "partial"
    if statuses == {"unsupported"}:
        semantic_status = "unsupported"
    return CollectionResult(assembly.manifest, summary, semantic_status)


def import_exports(
    sources: Sequence[Path], destination: Path, *, account_namespace: str,
    previous: Path | None = None, limits: Limits | None = None,
    catalog_limits: CatalogLimits | None = None, import_limits: ImportLimits | None = None,
) -> CollectionResult:
    """Create an immutable generation from explicitly selected folders or ZIPs.

    Identical logical revisions share one normalized record, while each supplied
    capture retains its provenance and bytes. This is not content-addressed blob
    storage: extending a generation copies its prior captures into the new one.
    """
    namespace = validate_namespace(account_namespace)
    active_limits = limits or Limits()
    semantic_limits = catalog_limits or CatalogLimits()
    parser_limits = import_limits or ImportLimits()
    if not sources or len(sources) > semantic_limits.max_captures:
        raise CatalogError("Select at least one source within the capture limit.")
    previous_collection = None
    if previous is not None:
        previous_collection = load_collection(previous, limits=active_limits, catalog_limits=semantic_limits)
        document = previous_collection.document
        if document["scope"] != "supplied_exports" or document["account_namespace"] != namespace:
            raise CatalogError("The previous generation must contain full captures for the same account namespace.")
        destination_path(destination, previous_collection.root)
    else:
        document = _new_collection(namespace)
    if len(document["captures"]) + len(sources) > semantic_limits.max_captures:
        raise CatalogError("The collection exceeds its capture limit.")
    for source in sources:
        info = source.lstat()
        if stat.S_ISDIR(info.st_mode):
            destination_path(destination, safe_directory(source))
    index = _RevisionIndex(document, semantic_limits)
    with assembling_archive(destination, limits=active_limits) as assembly:
        if previous_collection is not None:
            _copy_captures(previous_collection, assembly)
        for source in sources:
            _record_capture(document, assembly, source, index, active_limits, parser_limits)
        summary = _write_derivatives(assembly, document, semantic_limits)
    return _finish(assembly, document, summary)


def associate_conversation(
    archive: Path, destination: Path, *, conversation_key: str, state: str,
    project_id: str | None, reason: str, limits: Limits | None = None,
    catalog_limits: CatalogLimits | None = None,
) -> CollectionResult:
    """Record an explicit local classification in a new generation.

    Source associations remain unchanged. The decision is operator-supplied
    evidence, not authenticated identity or a historical platform assertion.
    """
    semantic_limits = catalog_limits or CatalogLimits()
    association = {"state": state, "project_id": project_id,
                   "evidence": {"kind": "explicit_local_operator_decision"}}
    validate_association(association)
    try:
        valid_reason = isinstance(reason, str) and bool(reason.strip()) and len(reason.encode("utf-8")) <= 2048
    except UnicodeError:
        valid_reason = False
    if not valid_reason:
        raise CatalogError("An association decision requires a reason of at most 2048 UTF-8 bytes.")
    collection = load_collection(archive, limits=limits, catalog_limits=semantic_limits)
    document = collection.document
    if document["scope"] != "supplied_exports":
        raise CatalogError("Association review requires a full collection generation.")
    if conversation_key not in {item["conversation_key"] for item in document["conversations"]}:
        raise CatalogError("The selected conversation is absent from the collection.")
    history = document["association_history"]
    if len(history) >= semantic_limits.max_decisions:
        raise CatalogError("The association decision history exceeds its limit.")
    decision = {"sequence": len(history) + 1, "conversation_key": conversation_key,
                "association": association, "reason": reason,
                "previous_decision_id": history[-1]["decision_id"] if history else None}
    decision["decision_id"] = content_digest(decision)
    history.append(decision)
    destination_path(destination, collection.root)
    with assembling_archive(destination, limits=limits) as assembly:
        _copy_captures(collection, assembly)
        summary = _write_derivatives(assembly, document, semantic_limits)
    return _finish(assembly, document, summary)


def recover_selection(
    archive: Path, destination: Path, *, conversation_keys: Sequence[str] = (),
    project_id: str | None = None, revision_id: str | None = None,
    limits: Limits | None = None, catalog_limits: CatalogLimits | None = None,
) -> CollectionResult:
    """Package selected derived conversations and exact bytes of bound artifacts.

    Whole source JSON documents can contain unrelated conversations and are
    deliberately excluded. Their provenance remains recorded; full originals
    remain recoverable from the parent collection with ordinary restore.
    """
    semantic_limits = catalog_limits or CatalogLimits()
    if isinstance(conversation_keys, (str, bytes)) or not isinstance(conversation_keys, Sequence):
        raise CatalogError("Conversation selections must be a sequence of identifiers.")
    if any(not isinstance(key, str) for key in conversation_keys):
        raise CatalogError("Conversation selections must contain only identifier strings.")
    if project_id is not None and (not isinstance(project_id, str) or not project_id):
        raise CatalogError("A project selection requires a nonempty identifier string.")
    if revision_id is not None and not isinstance(revision_id, str):
        raise CatalogError("A revision selection requires an identifier string.")
    if bool(conversation_keys) == (project_id is not None):
        raise CatalogError("Select conversation keys or one confirmed project, but not both.")
    if revision_id is not None and (project_id is not None or len(conversation_keys) != 1):
        raise CatalogError("A revision filter requires exactly one conversation key.")
    collection = load_collection(archive, limits=limits, catalog_limits=semantic_limits)
    original = collection.document
    selected_keys = set(conversation_keys)
    known = {item["conversation_key"] for item in original["conversations"]}
    if selected_keys - known:
        raise CatalogError("A selected conversation is absent from the collection.")
    if project_id is not None:
        associations = effective_associations(original)
        selected_keys = {key for key, value in associations.items()
                         if value["state"] == "project_confirmed" and value["project_id"] == project_id}
    if not selected_keys:
        raise CatalogError("The selection contains no confirmed matching conversations.")
    document = _new_collection(original["account_namespace"])
    document["scope"] = "selected_conversations"
    document["parent_manifest_sha256"] = hashlib.sha256(collection.manifest.to_bytes()).hexdigest()
    document["conversations"] = copy.deepcopy([item for item in original["conversations"]
                                                if item["conversation_key"] in selected_keys])
    if revision_id is not None:
        revisions = document["conversations"][0]["revisions"]
        document["conversations"][0]["revisions"] = [item for item in revisions if item["revision_id"] == revision_id]
        if not document["conversations"][0]["revisions"]:
            raise CatalogError("The selected revision is absent from the conversation.")
    # Carry the effective operator classification as a new, explicit derivative
    # decision. Unrelated conversation decisions must not leak into the package.
    for prior in original["association_history"]:
        if prior["conversation_key"] not in selected_keys:
            continue
        decision = copy.deepcopy(prior)
        decision["sequence"] = len(document["association_history"]) + 1
        decision["previous_decision_id"] = (document["association_history"][-1]["decision_id"]
                                            if document["association_history"] else None)
        decision.pop("decision_id")
        decision["decision_id"] = content_digest(decision)
        document["association_history"].append(decision)
    required: dict[str, set[str]] = {}
    source_captures = {item["capture_id"]: item for item in original["captures"]}
    source_document_paths = {capture_id: {item["path"] for item in capture["source_documents"]}
                             for capture_id, capture in source_captures.items()}
    for conversation in document["conversations"]:
        for revision in conversation["revisions"]:
            for occurrence in revision["occurrences"]:
                paths = required.setdefault(occurrence["capture_id"], set())
                for artifact in occurrence["artifacts"]:
                    if artifact["status"] == "stored":
                        if artifact["relative_path"] in source_document_paths[occurrence["capture_id"]]:
                            # A source may reference its own export JSON as an
                            # attachment. Carrying that whole document would
                            # disclose conversations outside this selection.
                            artifact["status"] = "excluded_by_selection"
                        else:
                            paths.add(artifact["relative_path"])
    destination_path(destination, collection.root)
    with assembling_archive(destination, limits=limits) as assembly:
        for capture_id in source_captures:
            if capture_id not in required:
                continue
            source_capture = source_captures[capture_id]
            selected_files = [item for item in source_capture["files"] if item["path"] in required[capture_id]]
            capture = {"capture_id": capture_id, "storage_id": source_capture["storage_id"],
                       "source_kind": "selection", "source_fingerprint": source_capture["source_fingerprint"],
                       "original_zip": None, "parser": source_capture["parser"], "status": "partial",
                       "source_documents": [], "files": selected_files, "issues": [],
                       "summary": {"scope": "selected_derived_records_and_bound_artifacts"}}
            for item in selected_files:
                path = f"captures/{capture['storage_id']}/source/{item['path']}"
                observed = assembly.add_file(collection.root / PAYLOAD_NAME / path, path)
                if observed.sha256 != item["sha256"] or observed.size_bytes != item["size_bytes"]:
                    raise CatalogError("A selected artifact changed after verification.")
            document["captures"].append(capture)
        summary = _write_derivatives(assembly, document, semantic_limits)
    return _finish(assembly, document, summary)
