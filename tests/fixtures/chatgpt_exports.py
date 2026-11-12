"""Two synthetic exports that exercise the collection preservation contract.

Expected combined inventory before operator classification:
    2 captures; 4 logical conversations; 5 revisions; 6 capture occurrences;
    16 mapping nodes across revisions, including structural roots;
    1 branched revision; 2 source-confirmed projects; 2 unknown associations;
    6 stored artifact references; 4 unavailable references; 10 source files.

The independent conversation becomes confirmed standalone only after an
explicit association decision. The second capture uses numbered JSON files.
The PNG is a valid one-pixel RGBA image. Model and package bytes are opaque
synthetic binary fixtures, not functional 3D assets or installable applications.
"""

from __future__ import annotations

import base64
import copy
import json
from pathlib import Path
from typing import Any

TINY_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGNQcEj4DwADBAHAgChw2gAAAABJRU5ErkJggg=="
)
MODEL_V1 = b"glTF\x02\x00\x00\x00\x00\xff\x80synthetic-model-v1"
MODEL_V2 = b"glTF\x02\x00\x00\x00\x00\xfe\x81synthetic-model-v2"
PACKAGE_BYTES = b"PK\x03\x04\x00\xff\x80synthetic-android-package"
UNRELATED_BYTES = b"\x00\xffUNRELATED_BINARY_MARKER\x80"
EVOLVING_ID = "conversation-evolving"
STABLE_ID = "conversation-stable"
INDEPENDENT_ID = "conversation-independent"
UNKNOWN_ID = "conversation-unknown"


def _message(identifier: str, role: str, text: str) -> dict[str, Any]:
    return {"id": identifier, "author": {"role": role},
            "content": {"content_type": "text", "parts": [text]}}


def _conversation(identifier: str, title: str, text: str, *, answer: bool = True) -> dict[str, Any]:
    mapping = {
        "root": {"id": "root", "parent": None, "children": ["question"], "message": None},
        "question": {"id": "question", "parent": "root",
                     "children": ["answer"] if answer else [],
                     "message": _message("message-question", "user", text)},
    }
    if answer:
        mapping["answer"] = {"id": "answer", "parent": "question", "children": [],
                             "message": _message("message-answer", "assistant", "Keep original bytes and evidence.")}
    return {"id": identifier, "title": title, "current_node": "answer" if answer else "question",
            "mapping": mapping, "future_metadata": {"uninterpreted_provider_marker": "first-version"}}


def export_records() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return independent mutable source records without private account data."""
    evolving = _conversation(EVOLVING_ID, "Archive design", "Compare preservation alternatives.")
    evolving["project_id"] = "project-aurora"
    evolving["mapping"]["question"]["message"]["metadata"] = {"attachments": [
        {"id": "image-1", "name": "diagram.png", "mime_type": "image/png",
         "relative_path": "assets/diagram.png"},
        {"id": "model-1", "name": "character.glb", "mime_type": "model/gltf-binary",
         "relative_path": "assets/character.glb"},
        {"id": "package-1", "name": "build.apk", "mime_type": "application/vnd.android.package-archive",
         "relative_path": "assets/build.apk"},
        {"id": "missing-1", "name": "not-provided.png", "mime_type": "image/png",
         "relative_path": "assets/not-provided.png"},
        {"id": "file-token-without-binding", "name": "unresolved.png", "mime_type": "image/png"},
    ]}
    stable = _conversation(STABLE_ID, "Storage checklist", "UNRELATED_CONVERSATION_MARKER storage plan.")
    stable["project_id"] = "project-harbor"
    independent = _conversation(INDEPENDENT_ID, "Independent plan", "Review this classification explicitly.", answer=False)
    unknown = _conversation(UNKNOWN_ID, "Unresolved membership", "Missing project metadata is inconclusive.", answer=False)
    unknown["gizmo_id"] = "custom-gpt-is-not-project-evidence"
    revised = copy.deepcopy(evolving)
    revised["title"] = "Archive design reviewed"
    revised["future_metadata"]["uninterpreted_provider_marker"] = "second-version"
    revised["mapping"]["question"]["children"].append("alternative")
    revised["mapping"]["alternative"] = {
        "id": "alternative", "parent": "question", "children": [],
        "message": _message("message-alternative", "assistant", "Preserve the alternative branch independently."),
    }
    revised["mapping"]["answer"]["children"] = ["follow-up"]
    revised["mapping"]["follow-up"] = {
        "id": "follow-up", "parent": "answer", "children": ["final-answer"],
        "message": _message("message-follow-up", "user", "Verify every supplied binary."),
    }
    revised["mapping"]["final-answer"] = {
        "id": "final-answer", "parent": "follow-up", "children": [],
        "message": _message("message-final", "assistant", "Use exact byte hashes; unresolved media stays unresolved."),
    }
    revised["current_node"] = "final-answer"
    return [evolving, stable, independent, unknown], [revised, copy.deepcopy(stable)]


def write_export_pair(root: Path) -> tuple[Path, Path]:
    """Create two fresh export directories; an existing destination is an error."""
    first, second = root / "export-first", root / "export-second"
    first.mkdir(parents=True)
    second.mkdir()
    records_first, records_second = export_records()
    (first / "conversations.json").write_text(json.dumps(records_first, indent=2), encoding="utf-8")
    for index, record in enumerate(records_second, 1):
        (second / f"conversations-{index}.json").write_text(json.dumps([record], indent=2), encoding="utf-8")
    for directory, model in ((first, MODEL_V1), (second, MODEL_V2)):
        (directory / "assets").mkdir()
        (directory / "assets/diagram.png").write_bytes(TINY_PNG)
        (directory / "assets/character.glb").write_bytes(model)
        (directory / "assets/build.apk").write_bytes(PACKAGE_BYTES)
    (first / "assets/unrelated.bin").write_bytes(UNRELATED_BYTES)
    return first, second
