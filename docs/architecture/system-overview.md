# System Overview

## Current reference slice

The reference implementation operates on a user-selected local directory.
It preserves regular-file bytes into a separate archive, records a versioned
manifest, checks the resulting inventory, and restores into a new destination.

The CLI is the user entry point. Consent must be checked before archive or
source contents are read. Internal library functions remain deterministic
primitives; future application and API boundaries must enforce their own
authenticated authorization and consent checks.

## Product architecture

| Boundary | Responsibility | State |
| --- | --- | --- |
| User interaction and consent | Explain scope and require deliberate acceptance | Foundation |
| Directory snapshot engine | Preserve, hash, validate, and recover supplied bytes | Reference implementation |
| Semantic source adapters | Interpret one supported export format | Planned |
| Conversation catalog | Identities, revisions, associations, artifact references | Planned |
| Readable views and search | Present derived, escaped content | Planned |
| Storage adapter | Authorized transfer and destination integrity evidence | Planned |
| Optional AI assistance | Suggest labels or descriptions with evidence | Design only |
| ChatGPT interface | Expose supported operations and status | Planned |

## Deterministic boundary

Hashing, path validation, original-byte preservation, manifest validation, and
recovery do not call a language model. Optional AI output cannot change
authoritative source bytes, grant permission, infer missing historical evidence
as fact, or certify integrity.

Imported content is data. Instructions embedded in a conversation, document,
filename, or model response do not authorize file operations or network access.

## Performance model

Let B be total file bytes and N the number of inventory entries.

- Hashing and copying require O(B) byte processing.
- Inventory and manifest memory grow with O(N), plus bounded path metadata.
- Canonical sorting requires O(N log N) comparisons.
- Streaming uses a fixed-size buffer; it does not load every payload into RAM.
- A full verification necessarily rereads bytes. Avoid claiming sublinear
  verification unless a different trust model and changed assumptions are stated.

The reference's exact limits and supported paths are described in
[reference-core.md](reference-core.md). Benchmark results are observations for
the recorded machine and workload, not universal throughput guarantees.

## Evolution

Optimize measured I/O amplification first: reuse a digest obtained during an
authorized copy when it proves the same bytes, avoid unnecessary rescans, and
separate content hashing from semantic parsing. Preserve validation boundaries
when making these changes.

Add concurrency only with bounded workers, cancellation, stable ordering,
backpressure, and failure isolation. Introduce content-addressed storage,
database indexes, or streaming manifest formats only after the current limits
are measured against real authorized workloads.

## Source safety

No operation in the initial product scope deletes or modifies provider data.
Restoration uses a new destination. Native-provider overwrite, rename,
reclassification, and deletion would require a separate capability, impact
preview, and explicit operation authorization; general terms cannot supply it.

## Related documents

- [Repository layout decision](decisions/0001-repository-layout.md)
- [Performance review](../engineering/performance-review.md)
- [AI engineering standard](../ai/ai-engineering-standard.md)
- [Consent and operation authorization](../../legal/consent-and-operation-authorization.md)
