# ADR 0002: Immutable Collections over Preserved Source Captures

**Date:** 2026-11-12
**Status:** Implemented for internal version 0.2.0
**Owner:** Fabio de Sousa Lopes, Lopix Neural Inc.

## Context

The directory archive primitive preserved bytes but did not interpret exported
conversations, revisions, branches, project evidence, or attachment references.
The product needs a useful workflow across repeated exports while retaining an
independently inspectable original and explicit coverage limitations.

The collection needs byte-exact binary handling, useful repeated-capture behavior,
and explicit interpretation evidence. No representative real account export has
been validated. A ChatGPT interface must expose verified capabilities without
claiming access to unavailable platform data.

## Decision

Add an experimental source adapter and a versioned collection derivative on top
of the existing directory archive contract. Preserve selected sources before
semantic interpretation. Every new collection generation is assembled in a
private staging directory and independently verified before no-replace publication.

Group responsibilities as follows:

| Package | Responsibility |
| --- | --- |
| `archive` | Exact file bytes, inventories, aggregate payload limits, staged assembly, verification, complete recovery |
| `formats` | Allocation-driving JSON byte, nesting, and token preflight |
| `importers` | Bounded ZIP input and explicitly supported source shapes |
| `catalog` | Namespaced identity, revision/occurrence reconciliation, association decisions, bounded queries, views, selected recovery |
| `integrations/chatgpt` | Optional MCP transport, configured grants, acceptance, bounded responses, and sanitized boundary errors |

Use hash maps for conversation/revision lookup and child sets for graph validation.
Never identify conversations by title, infer project absence from missing metadata,
or treat a matching content hash as a logical source identity.

Keep original file relationships and every capture occurrence. Reuse one normalized
revision for an identical complete source record. Preserve unknown fields in the
original JSON and include them in revision hashing. Artifact binding requires
explicit evidence; a filename, thumbnail, or URI alone does not establish the
presence of original bytes.

Association changes create a new generation with a separate operator decision
history. Selected recovery packages derived conversation records and exact bound
artifact bytes without copying whole recognized conversation exports or original
ZIPs containing unrelated material. Full source recovery remains available.

The MCP development adapter exposes only bounded read operations over configured
collection IDs. It uses the optional official SDK rather than a hand-written
protocol implementation. No transport or model participates in authoritative
hashing, identity decisions, or local archive publication.

## Tradeoffs

An immutable generation is straightforward to inspect and recover, but extending
one copies the previous payload. Cross-generation and cross-capture blob
deduplication is not implemented. This cost is stated explicitly rather than
hidden behind an incremental-backup claim.

The builder copies and hashes each supplied file in the same pass and avoids a
second payload copy merely to package derived metadata. It still performs a final
independent verification read. ZIP extraction and raw-container preservation
require their own bounded I/O and temporary storage.

JSON objects and catalog metadata are materialized under explicit resource
ceilings; total memory is not constant. Query operations verify all archive bytes
before reading the catalog and use literal scans rather than an indexed database.
The benchmark records those costs. A future index cache requires a specified
integrity/invalidation model; a future object store requires a durable commit and
garbage-collection protocol before replacing these simple guarantees.

Atomic publication provides a visibility boundary, not `fsync` crash durability.
Handled failures and cancellations remove staging files, while abrupt process or
system failure can leave temporary remnants. Checkpointed resume remains open.

## Acceptance evidence

Tests exercise repeated/renamed conversations, different account namespaces,
branches and structural roots, unknown associations, explicit decisions, stored
and unavailable media, opaque binary round trips, coverage reports, query budgets,
path attacks, corruption, selective-disclosure boundaries, and protocol acceptance.
The [verification record](../../engineering/collection-verification.md) records
observed results. Synthetic coverage does not establish compatibility with every
real ChatGPT export or legal readiness for public distribution.

## Version 0.3.0 integration

This decision retains the collection format and fidelity contract. The later
[service decision](0003-private-preservation-service.md) adds scoped execution
checkpoints, trusted human decisions, durable operation records, and restart
reconciliation around it. The 0.2.0 limitations above describe that baseline;
the current [system overview](../system-overview.md) records implemented service
behavior and the remaining power-loss/per-file-resume limits.
