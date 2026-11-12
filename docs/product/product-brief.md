# Product Brief

**Product:** LPX Keepmorrow
**Publisher:** Lopix Neural Inc.
**Engineering lead:** Fabio de Sousa Lopes
**Contact:** fabio@lopixneural.com
**Version:** 0.3.0 development candidate
**Reviewed:** November 12, 2026

## Purpose

Turn explicitly supplied conversation exports into a verifiable collection that
remains useful across repeated captures. Preserve the original files, interpret
supported conversation structures, expose missing evidence, and recover the
complete payload or a selected subset into ordinary files.

ChatGPT's native export supplies eligible account data. Keepmorrow uses selected
exports as inputs and adds revision continuity, explicit association decisions,
integrity checks, and selective recovery. An occasional downloaded copy may
already satisfy a user's needs. The [export comparison](export-comparison.md)
distinguishes documented capabilities from engineering judgments about usefulness.

## Intended workflow

1. Obtain an export through the source platform's supported process.
2. Accept the applicable processing scope and explicitly choose the input.
3. Preserve the supplied bytes and build the supported derived catalog.
4. Inspect conversations, revisions, branches, coverage gaps, and available files.
5. Review a separate plan before creating a new generation or portable package.
6. Authorize access to the resulting exact generation and verify recovered bytes.

The local CLI supports directories and compatible ZIPs. The private service adds
a trusted browser portal for file transfer and human decisions, together with
MCP tools and a compact MCP Apps interface. Native ChatGPT file-picker acquisition
and a live ChatGPT connection have not been demonstrated.

## Implemented capabilities

| Area | Version 0.3.0 behavior |
| --- | --- |
| Originals | Preserve supplied regular files, empty directories, and complete original ZIP containers with exact byte inventories |
| Conversations | Interpret the documented experimental mapping profile, source IDs, revisions, branches, and occurrence provenance |
| Associations | Distinguish confirmed projects, confirmed standalone conversations, and unknown associations; keep corrections separate from source evidence |
| Inspection | Browse, search literally, read revisions, verify integrity, and open an escaped standalone HTML view |
| Recovery | Recover complete payloads or selected derived records with exact bound artifacts into new destinations |
| Identity and consent | Validate configured OAuth resource tokens; record human acceptance, current policy digests, exact generations, actions, expiry, and revocation |
| Operations | Persist immutable plans, deliberate reviews, idempotent starts, cancellation, publication decisions, and process-restart reconciliation |
| Transfers | Receive bounded authorized uploads and deliver verified portable packages with current access and expiry checks |
| Interface | Provide a local operator portal and an OAuth-mode MCP Apps companion with independent human consent and operation review |

No source file or previous collection generation is overwritten or deleted.
A completed derivative requires its own access scope. Completed ancestor scopes
can be renewed through explicit human acceptance; accepting only a child cannot
override an expired or withdrawn ancestor. Active operations remain bound to
their exact reviewed grant and acceptance receipt.

## Compatibility and evidence

The semantic adapter is experimental. Synthetic exports exercise its documented
profile, but no representative real account export has been validated. Successful
byte preservation does not establish complete interpretation or account coverage.
A filename, URI, thumbnail, or unavailable download link does not establish that
an original image or binary was supplied.

All supplied regular files are retained independently of extension. Selective
recovery includes an artifact only when supported metadata binds it to preserved
bytes. Arbitrary selected attachments remain intact and are not internally
redacted. Recognized whole conversation documents and original ZIP containers
are excluded from a selected derivative because they can contain unrelated data.

The [private pilot validation record](../engineering/private-pilot-validation.md)
separates local tests, synthetic browser/protocol evidence, CI, measured workloads,
and unfulfilled live-account or deployment gates. Performance observations apply
to their recorded workload and environment; they are not capacity guarantees.

## Product and licensing direction

Project-owned source in this revision uses Apache License 2.0. The historical
development repository stays private; public distribution uses a reviewed source
snapshot with a fresh root commit. Source licensing, actual public publication,
and hosted-service qualification are separate decisions and evidence gates.
The maintained product's free direction does not restrict downstream rights.

Professional attribution belongs in product information and documentation, never
inside preserved source records. Source licensing does not transfer ownership of
user archives or replace processing consent, privacy obligations, or service terms.

## Limits and remaining gates

Keepmorrow does not enumerate a ChatGPT account, reconstruct missing originals,
restore native chats or Projects, modify provider data, or run model inference.
New generations copy previous payloads; physical deduplication and per-file resume
are not implemented. Queries verify the complete archive before scanning bounded
catalog metadata.

Live identity-provider registration, a selected host or tunnel, actual ChatGPT
interaction, authorized real-export validation, deployment-specific retention,
qualified legal review, and public release remain separate acceptance gates.
The [roadmap](roadmap.md) records their current status.
