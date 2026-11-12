"""Deterministic, passive HTML views of preserved collection evidence.

Copyright 2026 Lopix Neural Inc. All rights reserved.
"""

from __future__ import annotations

import html
import json
import re
from typing import Any
from urllib.parse import quote

from keepmorrow.archive.model import ArchiveError, validate_relative_path

_STORAGE_ID = re.compile(r"[0-9]{6}\Z")
_CSP = (
    "default-src 'none'; script-src 'none'; style-src 'unsafe-inline'; "
    "img-src 'none'; connect-src 'none'; font-src 'none'; object-src 'none'; "
    "frame-src 'none'; base-uri 'none'; form-action 'none'"
)
_CSS = """
:root{color-scheme:light;--ink:#182a36;--muted:#536673;--line:#dce5e9;--accent:#175a66;--paper:#fff}
*{box-sizing:border-box}body{margin:0;background:#f5f8fa;color:var(--ink);font:15px/1.55 system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
header,main,footer{max-width:1180px;margin:auto;padding:28px 32px}header{padding-top:38px;padding-bottom:18px}
.brand{font-size:12px;font-weight:750;letter-spacing:.14em;color:var(--accent);text-transform:uppercase}
h1{font-size:clamp(28px,4vw,42px);line-height:1.16;letter-spacing:-.025em;margin:14px 0 12px}h2{font-size:23px;line-height:1.25;margin:30px 0 15px}
h3{font-size:17px;line-height:1.35;margin:20px 0 10px}p{margin:9px 0}.muted,.meta{color:var(--muted)}.meta{font-size:13px}
.scope{max-width:850px}.stats{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin:24px 0 8px}
.stat,.card{background:var(--paper);border:1px solid var(--line);border-radius:12px}.stat{padding:16px 20px}.stat strong{display:block;font-size:25px;font-weight:700}.stat span{color:var(--muted);font-size:12px;text-transform:uppercase;letter-spacing:.045em}
.card{margin:12px 0;overflow:hidden}.card>summary{padding:18px 20px}.body{padding:0 20px 20px}.card[open]>summary{border-bottom:1px solid var(--line);margin-bottom:16px}
summary{cursor:pointer;font-weight:650;overflow-wrap:anywhere}summary:focus-visible,a:focus-visible{outline:3px solid #6eacb8;outline-offset:3px}
.revision{border:1px solid var(--line);border-radius:8px;margin:14px 0;padding:13px 15px}.revision>summary{font-size:15px}.revision[open]>summary{margin-bottom:12px}
.badge{display:inline-block;max-width:100%;vertical-align:middle;background:#eaf2f3;color:#23535c;border-radius:5px;padding:3px 7px;margin:2px 5px 2px 0;font-size:11px;font-weight:650;overflow-wrap:anywhere}
.warning{background:#fff3d9;color:#795c20}.notice{border-left:3px solid #a5bac3;padding:8px 14px;margin:14px 0;color:var(--muted);background:#f7fafb}
.table-wrap{overflow-x:auto}table{width:100%;border-collapse:collapse;margin:12px 0;font-size:13px}th,td{text-align:left;vertical-align:top;padding:10px 9px;border-bottom:1px solid var(--line);overflow-wrap:anywhere}th{font-size:11px;text-transform:uppercase;letter-spacing:.04em;color:var(--muted)}
a{color:var(--accent);text-decoration-thickness:1px;text-underline-offset:3px}code{font:12px/1.5 ui-monospace,SFMono-Regular,Consolas,monospace;overflow-wrap:anywhere}pre{white-space:pre-wrap;overflow-wrap:anywhere;word-break:normal;font:13px/1.6 ui-monospace,SFMono-Regular,Consolas,monospace;background:#f7f9fa;border:1px solid #e5ecef;border-radius:7px;padding:13px;margin:10px 0}
dl{display:grid;grid-template-columns:minmax(100px,150px) minmax(0,1fr);gap:5px 14px;margin:12px 0}dt{font-size:12px;color:var(--muted)}dd{margin:0;font-size:13px;overflow-wrap:anywhere}
.node{margin:9px 0;border-left:2px solid #cddde2;padding:6px 0 6px 13px}.node>summary{font-size:13px;font-weight:550}.empty{padding:12px 0;color:var(--muted)}footer{border-top:1px solid var(--line);margin-top:26px;font-size:12px;color:var(--muted)}
@media(max-width:680px){header,main,footer{padding-left:18px;padding-right:18px}.stats{grid-template-columns:repeat(2,minmax(0,1fr))}.body{padding-left:14px;padding-right:14px}.card>summary{padding:15px 14px}dl{grid-template-columns:1fr;gap:2px}dd{margin-bottom:7px}}
"""


def _escaped(value: object) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def _objects(value: object) -> list[dict[str, Any]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _structured(value: object) -> str:
    return _escaped(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2))


def _size(value: object) -> str:
    if type(value) is not int or value < 0:
        return "Size unavailable"
    for threshold, unit in ((1024**3, "GiB"), (1024**2, "MiB"), (1024, "KiB")):
        if value >= threshold:
            return f"{value / threshold:.2f} {unit}"
    return f"{value} bytes"


def _file_links(capture: dict[str, Any]) -> dict[str, str]:
    """Index local download links once for the exact supplied inventory.

    A source reference, filename label, URL, or model suggestion is insufficient
    evidence for a link. This restriction also prevents markup or URL schemes
    imported from conversations from becoming navigation behavior in the view.
    """
    storage_id = capture.get("storage_id")
    if not isinstance(storage_id, str) or _STORAGE_ID.fullmatch(storage_id) is None:
        return {}
    result: dict[str, str] = {}
    for record in _objects(capture.get("files")):
        try:
            relative_path = validate_relative_path(record.get("path"))
        except ArchiveError:
            continue
        result[relative_path] = "/".join(
            quote(part, safe="")
            for part in ("captures", storage_id, "source", *relative_path.split("/"))
        )
    return result


def _file_link(links: dict[str, str], path: object, *, label: object | None = None) -> str:
    text = _escaped(path if label is None else label)
    url = links.get(path) if isinstance(path, str) else None
    if url is None:
        return f'<span>{text}</span> <span class="meta">(no matching supplied file)</span>'
    # Request a download for active source formats instead of embedding them in
    # this passive view. Handling the downloaded file belongs to the browser;
    # no source file is previewed or evaluated by this renderer.
    filename = str(path).rsplit("/", 1)[-1]
    return f'<a href="{_escaped(url)}" download="{_escaped(filename)}">{text}</a>'


def _association(value: object) -> str:
    association = value if isinstance(value, dict) else {}
    state = association.get("state")
    labels = {
        "project_confirmed": "Confirmed project",
        "standalone_confirmed": "Confirmed standalone",
        "association_unknown": "Unknown association",
    }
    label = labels.get(state, "Unrecognized association state")
    css = "badge" if state in {"project_confirmed", "standalone_confirmed"} else "badge warning"
    result = f'<span class="{css}">{label}</span>'
    if association.get("project_id") is not None:
        result += f'<span class="meta">Project: <code>{_escaped(association["project_id"])}</code></span>'
    if association.get("evidence") is not None:
        result += f'<details><summary class="meta">Association evidence</summary><pre>{_structured(association["evidence"])}</pre></details>'
    return result


def _nodes(nodes: list[dict[str, Any]]) -> str:
    if not nodes:
        return '<p class="empty">No supported message nodes were indexed for this revision.</p>'
    result = ['<h3>Message graph</h3><p class="meta">Parent and child identifiers preserve branch structure. This listing is not a flattened conversation timeline.</p>']
    for node in nodes:
        role = node.get("role") or "Structural node"
        children = node.get("children_ids")
        child_ids = ", ".join(str(item) for item in children) if isinstance(children, list) else ""
        result.append(
            f'<details class="node"><summary>{_escaped(role)} · <code>{_escaped(node.get("id"))}</code></summary>'
            f'<dl><dt>Parent node</dt><dd><code>{_escaped(node.get("parent_id") or "None")}</code></dd>'
            f'<dt>Child nodes</dt><dd><code>{_escaped(child_ids or "None")}</code></dd>'
            f'<dt>Message ID</dt><dd><code>{_escaped(node.get("message_id") or "None")}</code></dd>'
            f'<dt>Content type</dt><dd>{_escaped(node.get("content_type") or "Not supplied")}</dd></dl>'
        )
        if node.get("text"):
            result.append(f'<pre>{_escaped(node["text"])}</pre>')
        else:
            result.append('<p class="meta">No indexed text. Consult the preserved source for unsupported or non-text content.</p>')
        result.append("</details>")
    return "".join(result)


def _occurrences(
    occurrences: list[dict[str, Any]],
    links_by_capture_id: dict[str, dict[str, str]],
) -> str:
    result = ["<h3>Capture provenance and artifacts</h3>"]
    if not occurrences:
        return '<p class="empty">No capture occurrences were recorded for this revision.</p>'
    for occurrence in occurrences:
        capture_id = occurrence.get("capture_id")
        links = links_by_capture_id.get(capture_id, {}) if isinstance(capture_id, str) else {}
        provenance = occurrence.get("provenance")
        provenance = provenance if isinstance(provenance, dict) else {}
        source_path = provenance.get("source_path")
        result.append(
            '<details class="revision"><summary>Capture '
            f'<code>{_escaped(capture_id)}</code></summary><dl>'
            f'<dt>Source record</dt><dd>{_file_link(links, source_path or "Not supplied")}</dd>'
            f'<dt>Record index</dt><dd>{_escaped(provenance.get("record_index", "Not supplied"))}</dd>'
            f'<dt>Record SHA-256</dt><dd><code>{_escaped(provenance.get("record_sha256", "Not supplied"))}</code></dd></dl>'
        )
        artifacts = _objects(occurrence.get("artifacts"))
        if artifacts:
            result.append('<div class="table-wrap"><table><thead><tr><th>Artifact</th><th>Availability</th><th>Source reference</th><th>Supplied file</th></tr></thead><tbody>')
            for artifact in artifacts:
                status = artifact.get("status", "unresolved")
                path = artifact.get("relative_path")
                file_cell = _file_link(links, path) if status == "stored" and path else "No stored file established"
                result.append(
                    f'<tr><td>{_escaped(artifact.get("original_name") or artifact.get("reference_id"))}'
                    f'<br><span class="meta">{_escaped(artifact.get("kind"))}</span></td>'
                    f'<td><span class="badge{(" warning" if status != "stored" else "")}">{_escaped(status)}</span>'
                    f'<br><span class="meta">{_escaped(artifact.get("media_type") or "Type not supplied")}</span></td>'
                    f'<td><code>{_escaped(artifact.get("source_reference"))}</code>'
                    f'<br><span class="meta">Node: {_escaped(artifact.get("node_id") or "Not supplied")}</span></td>'
                    f'<td>{file_cell}<br><span class="meta">{_size(artifact.get("size_bytes"))}</span>'
                    f'<br><code>{_escaped(artifact.get("sha256"))}</code></td></tr>'
                )
            result.append("</tbody></table></div>")
        else:
            result.append('<p class="meta">No supported artifact references were indexed in this occurrence.</p>')
        result.append("</details>")
    return "".join(result)


def _conversation(conversation: dict[str, Any], links_by_capture_id: dict[str, dict[str, str]]) -> str:
    revisions = _objects(conversation.get("revisions"))
    representative_title = revisions[0].get("title") if revisions else None
    result = [
        '<details class="card"><summary>'
        f'{_escaped(representative_title or "Untitled conversation")} '
        f'<span class="badge">{len(revisions)} {("revision" if len(revisions) == 1 else "revisions")}</span></summary><div class="body">'
        f'<dl><dt>Source ID</dt><dd><code>{_escaped(conversation.get("source_id"))}</code></dd>'
        f'<dt>Conversation key</dt><dd><code>{_escaped(conversation.get("conversation_key"))}</code></dd></dl>'
    ]
    for revision in revisions:
        result.append(
            '<details class="revision"><summary>'
            f'{_escaped(revision.get("title") or "Untitled revision")}</summary>'
            f'<dl><dt>Revision ID</dt><dd><code>{_escaped(revision.get("revision_id"))}</code></dd>'
            f'<dt>Current node</dt><dd><code>{_escaped(revision.get("current_node_id") or "Not supplied")}</code></dd></dl>'
        )
        result.append(_association(revision.get("association")))
        result.append(_nodes(_objects(revision.get("nodes"))))
        result.append(_occurrences(_objects(revision.get("occurrences")), links_by_capture_id))
        result.append("</details>")
    result.append("</div></details>")
    return "".join(result)


def _capture(capture: dict[str, Any], links: dict[str, str]) -> str:
    files = _objects(capture.get("files"))
    result = [
        '<details class="card"><summary>Capture '
        f'<code>{_escaped(capture.get("storage_id"))}</code> '
        f'<span class="badge">{len(files)} supplied {("file" if len(files) == 1 else "files")}</span></summary><div class="body">'
        f'<dl><dt>Capture ID</dt><dd><code>{_escaped(capture.get("capture_id"))}</code></dd>'
        f'<dt>Source kind</dt><dd>{_escaped(capture.get("source_kind") or "Not supplied")}</dd></dl>'
    ]
    if capture.get("summary"):
        result.append(f'<details><summary>Import summary</summary><pre>{_structured(capture["summary"])}</pre></details>')
    issues = capture.get("issues")
    if isinstance(issues, list) and issues:
        result.append(f'<details open><summary>Import observations: {len(issues)}</summary><pre>{_structured(issues)}</pre></details>')
    else:
        result.append('<p class="meta">No import observations were recorded. This does not establish account-wide completeness.</p>')
    if files:
        result.append('<div class="table-wrap"><table><thead><tr><th>Supplied file</th><th>Size</th><th>SHA-256</th></tr></thead><tbody>')
        for record in files:
            result.append(
                f'<tr><td>{_file_link(links, record.get("path"))}</td>'
                f'<td>{_size(record.get("size_bytes"))}</td><td><code>{_escaped(record.get("sha256"))}</code></td></tr>'
            )
        result.append("</tbody></table></div>")
    else:
        result.append('<p class="empty">No source files are listed for this capture.</p>')
    result.append("</div></details>")
    return "".join(result)


def render_collection(document: dict[str, Any]) -> bytes:
    """Render a validated collection or selection as passive, portable UTF-8 HTML.

    Place the result at payload/index.html. Source text is always escaped;
    downloads use only safe relative paths present in capture inventories. The
    renderer neither loads source files nor follows links, and emits no script,
    active preview, or remote resource. This is a derived browsing aid, not an
    integrity check or a native ChatGPT restoration mechanism.

    Runtime and memory scale with the rendered document, including escaped text.
    The caller owns collection resource limits and output archive validation.
    """
    if not isinstance(document, dict):
        raise ArchiveError("A collection view requires a validated collection object.")
    captures = _objects(document.get("captures"))
    conversations = _objects(document.get("conversations"))
    captures_with_links = [(capture, _file_links(capture)) for capture in captures]
    links_by_capture_id: dict[str, dict[str, str]] = {}
    ambiguous_ids: set[str] = set()
    for capture, links in captures_with_links:
        capture_id = capture.get("capture_id")
        if not isinstance(capture_id, str):
            continue
        if capture_id in links_by_capture_id:
            ambiguous_ids.add(capture_id)
        else:
            links_by_capture_id[capture_id] = links
    for capture_id in ambiguous_ids:
        # A repeated capture identity cannot establish which occurrence owns a
        # link. Suppress that mapping instead of choosing an arbitrary winner.
        links_by_capture_id.pop(capture_id, None)
    selected = (document.get("scope") == "selected_conversations"
                or "selection" in str(document.get("format", "")))
    title = "Selected preserved work" if selected else "Your preserved work"
    revision_count = sum(len(_objects(item.get("revisions"))) for item in conversations)
    file_count = sum(len(_objects(item.get("files"))) for item in captures)
    result = [
        '<!doctype html><html lang="en-US"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f'<meta http-equiv="Content-Security-Policy" content="{_escaped(_CSP)}">'
        '<meta name="referrer" content="no-referrer">'
        f'<title>{title} · LPX Keepmorrow</title><style>{_CSS}</style></head><body>'
        '<header><div class="brand">LPX Keepmorrow</div>'
        f'<h1>{title}</h1><p class="scope muted">Derived collection view. Original files remain separate from this index. '
        'Coverage is limited to supplied inputs and the supported import profile.</p>'
        '<div class="stats">'
    ]
    for count, label in (
        (len(captures), "Captures"),
        (len(conversations), "Conversations"),
        (revision_count, "Revisions"),
        (file_count, "Supplied files"),
    ):
        result.append(f'<div class="stat"><strong>{count}</strong><span>{label}</span></div>')
    result.append(
        '</div></header><main><p class="meta">Provider: '
        f'{_escaped(document.get("provider", "Not supplied"))} · Source account: '
        f'<code>{_escaped(document.get("account_namespace", "Not supplied"))}</code></p>'
    )
    if selected:
        result.append('<p class="notice">This package contains selected records and the supplied files included for that selection.</p>')
    if document.get("scope") is not None:
        result.append(f'<details><summary>Declared scope</summary><pre>{_structured(document["scope"])}</pre></details>')
    result.append('<h2>Conversations and revisions</h2><p class="meta">Expand a conversation to inspect all preserved revisions, message relationships, and capture evidence. Browser Find can locate text in this file.</p>')
    result.extend(_conversation(item, links_by_capture_id) for item in conversations)
    if not conversations:
        result.append('<p class="empty">No supported conversations were indexed. Review capture observations and original files.</p>')
    result.append('<h2>Supplied files and import observations</h2><p class="meta">Downloads refer to files included in this package. Referenced, missing, or unresolved media are shown separately within conversation occurrences.</p>')
    result.extend(_capture(capture, links) for capture, links in captures_with_links)
    if not captures:
        result.append('<p class="empty">No captures are listed in this document.</p>')
    history = document.get("association_history")
    if isinstance(history, list) and history:
        result.append(f'<h2>Association history</h2><details class="card"><summary>Recorded association decisions</summary><div class="body"><pre>{_structured(history)}</pre></div></details>')
    result.append(
        '<p class="notice">This HTML file is a derived view, not an integrity result. Use Keepmorrow verification to check the package. '
        'Portable recovery produces ordinary files; it does not recreate native ChatGPT chats or Projects.</p>'
        '</main><footer>LPX Keepmorrow · Lopix Neural Inc. · Fabio de Sousa Lopes<br>'
        'Publisher and developer credit applies to this application view. Preserved source files remain unchanged.'
        '</footer></body></html>'
    )
    return "".join(result).encode("utf-8")
