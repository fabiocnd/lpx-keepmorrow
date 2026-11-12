"""Versioned contracts for bounded, evidence-preserving source interpretation.

Copyright 2026 Lopix Neural Inc. All rights reserved.
"""

from __future__ import annotations

from dataclasses import dataclass, fields
from typing import Any

from keepmorrow.archive.model import ArchiveError, FileRecord

CAPTURE_FORMAT = "lpx-keepmorrow.chatgpt-capture"
CAPTURE_VERSION = 1
PARSER_NAME = "chatgpt-mapping"
PARSER_VERSION = 1
PROVIDER = "openai.chatgpt"


class ImportFailure(ArchiveError):
    """Import cannot continue within its integrity or resource contract."""


@dataclass(frozen=True, slots=True)
class ImportLimits:
    """Budgets apply to all attempted records, including rejected records.

    JSON is decoded one file at a time. Its object graph is bounded by both
    bytes and lexical tokens; these limits do not claim constant process RSS.
    """

    max_json_file_bytes: int = 32 * 1024**2
    max_json_total_bytes: int = 128 * 1024**2
    max_files: int = 10_000
    max_conversations: int = 10_000
    max_nodes: int = 100_000
    max_edges: int = 200_000
    max_text_bytes: int = 64 * 1024**2
    max_artifact_references: int = 100_000
    max_issues: int = 10_000
    max_json_depth: int = 64
    max_json_tokens: int = 2_000_000
    max_identifier_bytes: int = 1024

    def __post_init__(self) -> None:
        for field in fields(self):
            if type(getattr(self, field.name)) is not int or getattr(self, field.name) <= 0:
                raise ImportFailure(f"{field.name} must be a positive integer.")
        if self.max_json_depth > 128:
            raise ImportFailure("max_json_depth must not exceed 128.")


@dataclass(frozen=True, slots=True)
class ImportIssue:
    """Bounded interpretation finding with source location rather than copied text."""

    code: str
    source_path: str | None
    record_index: int | None
    node_id: str | None
    message: str

    def as_dict(self) -> dict[str, Any]:
        return {"code": self.code, "source_path": self.source_path,
                "record_index": self.record_index, "node_id": self.node_id,
                "message": self.message}


@dataclass(frozen=True, slots=True)
class SourceDocument:
    """Preserved JSON identity and the parser's accounting for attempted records."""

    path: str
    sha256: str
    size_bytes: int
    status: str
    record_count: int | None
    accepted_records: int
    rejected_records: int

    def as_dict(self) -> dict[str, Any]:
        return {"path": self.path, "sha256": self.sha256, "size_bytes": self.size_bytes,
                "status": self.status, "record_count": self.record_count,
                "accepted_records": self.accepted_records,
                "rejected_records": self.rejected_records}


@dataclass(frozen=True, slots=True)
class MessageNode:
    """Supported graph fields; omitted source content remains in the original file."""

    id: str
    parent_id: str | None
    children_ids: tuple[str, ...]
    message_id: str | None
    role: str | None
    text: str
    content_type: str | None

    def as_dict(self) -> dict[str, Any]:
        return {"id": self.id, "parent_id": self.parent_id,
                "children_ids": list(self.children_ids), "message_id": self.message_id,
                "role": self.role, "text": self.text, "content_type": self.content_type}


@dataclass(frozen=True, slots=True)
class ArtifactReference:
    """Availability evidence with byte identity only when inventory-bound."""

    reference_id: str
    node_id: str
    kind: str
    source_reference: str | None
    original_name: str | None
    media_type: str | None
    relative_path: str | None
    status: str
    size_bytes: int | None
    sha256: str | None

    def as_dict(self) -> dict[str, Any]:
        return {"reference_id": self.reference_id, "node_id": self.node_id,
                "kind": self.kind, "source_reference": self.source_reference,
                "original_name": self.original_name, "media_type": self.media_type,
                "relative_path": self.relative_path, "status": self.status,
                "size_bytes": self.size_bytes, "sha256": self.sha256}


@dataclass(frozen=True, slots=True)
class ConversationRevision:
    """One namespaced source occurrence and its deterministically derived graph."""

    conversation_key: str
    source_id: str
    revision_id: str
    title: str
    association_state: str
    project_id: str | None
    association_evidence: str
    current_node_id: str | None
    nodes: tuple[MessageNode, ...]
    artifacts: tuple[ArtifactReference, ...]
    source_path: str
    record_index: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "conversation_key": self.conversation_key, "source_id": self.source_id,
            "revision_id": self.revision_id, "title": self.title,
            "association": {
                "state": self.association_state, "project_id": self.project_id,
                "evidence": {"kind": self.association_evidence,
                             "source_path": self.source_path,
                             "record_index": self.record_index,
                             "field": "project_id"},
            },
            "current_node_id": self.current_node_id,
            "nodes": [item.as_dict() for item in self.nodes],
            "artifacts": [item.as_dict() for item in self.artifacts],
            "provenance": {"source_path": self.source_path,
                           "record_index": self.record_index,
                           "record_sha256": self.revision_id},
        }


@dataclass(frozen=True, slots=True)
class ParsedCapture:
    """Interpretation of the supplied inventory, without an account-coverage claim."""

    account_namespace: str
    capture_id: str
    status: str
    source_documents: tuple[SourceDocument, ...]
    conversations: tuple[ConversationRevision, ...]
    files: tuple[FileRecord, ...]
    issues: tuple[ImportIssue, ...]

    def as_dict(self) -> dict[str, Any]:
        """Return a caller-owned JSON document without exposing mutable internals."""
        return {
            "format": CAPTURE_FORMAT, "version": CAPTURE_VERSION,
            "parser": {"name": PARSER_NAME, "version": PARSER_VERSION,
                       "compatibility": "experimental"},
            "provider": PROVIDER, "account_namespace": self.account_namespace,
            "capture_id": self.capture_id, "status": self.status,
            "scope": "supplied_files_only",
            "source_documents": [item.as_dict() for item in self.source_documents],
            "conversations": [item.as_dict() for item in self.conversations],
            "files": [item.as_dict() for item in self.files],
            "issues": [item.as_dict() for item in self.issues],
            "summary": {
                "source_document_count": len(self.source_documents),
                "parsed_documents": sum(item.status == "parsed" for item in self.source_documents),
                "malformed_documents": sum(item.status == "malformed" for item in self.source_documents),
                "unsupported_documents": sum(item.status == "unsupported" for item in self.source_documents),
                "source_records": sum(item.record_count or 0 for item in self.source_documents),
                "accepted_records": len(self.conversations),
                "rejected_records": sum(item.rejected_records for item in self.source_documents),
                "message_nodes": sum(len(item.nodes) for item in self.conversations),
                "artifact_references": sum(len(item.artifacts) for item in self.conversations),
                "supplied_files": len(self.files), "issue_count": len(self.issues),
            },
        }
