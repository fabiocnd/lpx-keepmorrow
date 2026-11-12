# System Overview

## Current implementation: 0.2.0

LPX Keepmorrow preserves explicitly selected local directories or supported ZIPs
and builds a derived conversation collection over those originals. The local
workflow includes repeated captures, namespaced identities, revision history,
message graphs, association decisions, literal search, standalone HTML, and
selected recovery. The generic directory archive commands remain available.

The ChatGPT mapping adapter is experimental. Its supported JSON shapes are
documented and exercised with synthetic fixtures; no representative real account
export has been validated. Successful preservation of supplied bytes and
successful interpretation of the declared profile are separate outcomes. Neither
establishes completeness of a ChatGPT account. See the
[import contract](import-contract.md) for the exact compatibility boundary.

## Responsibility boundaries

| Boundary | Implemented responsibility | Limit |
| --- | --- | --- |
| CLI and consent | Require current terms/privacy declarations before inspecting selected content; format operation results | Local declarations do not authenticate a person or establish legal approval |
| `archive` | Inventory, copy, hash, assemble, verify, and recover exact supplied bytes | Local filesystem destinations; no remote storage adapter |
| `formats` | Bound JSON bytes, nesting, and lexical tokens before object construction | Structural preflight supplements strict decoding and domain validation |
| `importers` | Validate directory/ZIP intake and interpret the experimental ChatGPT mapping profile | Unsupported material remains preserved and explicitly reported |
| `catalog` | Reconcile identities and revisions; validate graphs; record associations; query, render, and recover selections | Bounded in-memory metadata and literal scans; no persistent search database |
| `integrations/chatgpt` | Optional read-only MCP tools over explicitly registered local collections | SDK-tested loopback adapter; no authenticated, deployed, or installed ChatGPT connection |
| Optional AI assistance | No model feature is implemented in the preservation path | Suggestions remain a future, separately governed capability |

The core uses the Python standard library. The MCP adapter adds an optional SDK
dependency; it does not become part of authoritative hashing or identity logic.
Internal library functions are domain primitives. Any new user-facing boundary
must enforce its own authorization and acceptance contract.

## Collection construction

1. Validate acceptance, arguments, resource limits, and destination separation.
2. Validate the selected directory or extract a supported ZIP into an isolated
   temporary tree. ZIP metadata and actual decompressed bytes have separate bounds.
3. Copy and hash originals into private archive staging. ZIP inputs retain both
   the complete original container and its extracted files.
4. Parse preserved JSON, reconcile supported records, and retain source provenance
   and explicit coverage outcomes. The source is never rewritten.
5. Write the derived catalog, coverage report, and escaped standalone HTML view.
6. Validate the manifest and collection contract, independently verify payload
   bytes, and publish to a new destination without replacing existing data.

The package layout and commands are documented in the
[local collection workflow](collection-workflow.md). A partial or unsupported
semantic result can still produce a verified archive; the CLI reports that
distinction with exit status `3`. Successful selected recovery also returns `3`
because its capture coverage is intentionally partial.

## Originals, identity, and evidence

Logical conversation identity includes the provider, the operator's account
namespace, and the source conversation identifier. Revisions hash the complete
decoded source record, including unknown fields. Canonical record hashing and
exact original-file hashing serve different purposes: formatting changes alone
do not create a new canonical revision, while the original bytes remain distinct
capture evidence.

The catalog preserves graph parents, children, branches, and null-message
structural nodes within the supported profile. Unknown source fields remain in
the originals. A missing project field produces `association_unknown`, not
`standalone_confirmed`. Explicit operator decisions have their own history and
do not alter source evidence. Their hash chain establishes internal consistency,
not authenticated authorship.

All supplied regular files are preserved regardless of extension. Semantic
artifact binding currently requires an explicit supported `relative_path` that
matches the capture inventory. Missing files, unresolved references, external
URLs, and unsupported references remain visible. Imported URLs are not fetched,
and binary contents are not decoded or executed by the preservation core.

## Generations and recovery

Importing additional captures or recording an association creates a new immutable
generation. The previous generation remains unchanged. Identical source records
reuse a normalized revision, but each capture occurrence and its original files
remain represented. Previous payload files are physically copied into the new
generation; cross-capture and cross-generation blob deduplication is not implemented.

Complete restore recovers every payload file into a new directory. Selected
recovery creates a derivative package containing chosen conversation records and
available bound artifacts. It omits raw source ZIPs, unrelated files, and recognized
whole conversation JSON documents. References to those excluded documents receive
`excluded_by_selection`. Arbitrary selected attachments are not internally
redacted and may themselves contain additional information. Full originals remain
available in the parent collection. Neither recovery operation recreates native
ChatGPT chats or projects.

## Read interfaces

The CLI provides paginated browsing and reading plus literal, Unicode
case-insensitive search across retained revisions. It verifies the complete
archive before querying its catalog. The standalone HTML view contains escaped
text and local artifact links, with no scripts or network requests. Opening that
view directly does not perform integrity verification.

The optional MCP server binds to `127.0.0.1` and exposes bounded read operations
over configured opaque collection IDs. Protocol tests exercise the official SDK;
they do not establish installation or connectivity in a real ChatGPT account.
Authentication, per-user grants, a reachable deployment, and actual account
acceptance testing remain open. See the
[ChatGPT integration contract](chatgpt-integration.md).

## Performance and failure model

Let B be payload bytes, N inventory entries, V graph nodes, E graph edges, and T
indexed text length. Copying and hashing require O(B) byte processing; canonical
inventory sorting requires O(N log N) comparisons. Graph validation uses O(V + E)
work. Literal search scans retained text and incurs full archive verification
before that scan.

Assembly copies and hashes a supplied file in one pass and avoids another payload
copy merely to package derived metadata. Final verification still rereads all
payload bytes. ZIP extraction adds decompression and temporary storage. Extending
a generation copies previous and new content, so its cost is not proportional
only to newly supplied bytes.

File streaming uses bounded chunks. JSON documents and catalog metadata are
materialized under byte, depth, token, record, graph, and aggregate metadata
ceilings; total memory is not constant. Exact limits appear in the
[import contract](import-contract.md) and [archive reference](reference-core.md).
Benchmark results apply to their recorded workloads and environments.

Handled failures and cancellation clean up staging. Atomic publication provides
a visibility boundary, not `fsync` crash durability. Abrupt process or system
failure may leave temporary remnants. Durable checkpoints, restart, and resume
are not implemented. The filesystem contract assumes a stable user-controlled
tree, rather than hostile concurrent replacement of directory ancestors.

## Preservation and execution boundary

No model decides authoritative identity, integrity, packaging, or recovery.
Imported instructions, filenames, documents, and links are untrusted data and
cannot authorize execution or network access. Sources remain unchanged; every
write operation uses a separate new destination.

Provider-side overwrite, reclassification, or deletion would require a separate
implemented capability, impact preview, and explicit operation authorization.
General acceptance does not authorize those actions. Cloud transfer, authenticated
hosting, retention policy, and public distribution remain separate work.

## Related documents

- [Immutable collection decision](decisions/0002-immutable-collections.md)
- [Collection verification](../engineering/collection-verification.md)
- [Performance policy](../engineering/performance-policy.md)
- [AI engineering standard](../ai/ai-engineering-standard.md)
- [Consent and operation authorization](../../legal/consent-and-operation-authorization.md)
