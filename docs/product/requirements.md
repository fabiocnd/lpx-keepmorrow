# Requirements and Delivery Status

This matrix carries forward the ten requirements in the
[Blueprint v0.2](../provenance/blueprint-v0.2-snapshot.md). A reference primitive
does not satisfy an entire product requirement.

| ID | Requirement | Foundation scope | Remaining acceptance evidence |
| --- | --- | --- | --- |
| R1 | Explicit intake | User-selected local directory and declared format | Real export recognition, receipt provenance, parser versions, item-level outcomes |
| R2 | Preserve originals and structure | Byte-preserving snapshot of regular files and directory inventory | Semantic message nodes, branches, unknown source fields, readable views |
| R3 | Available artifacts | Supplied files retained; no remote fetching | Artifact references, missing-media statuses, source relationships |
| R4 | Evidence-based association | Three association states specified in synthetic data | Runtime association validation, correction history, user review |
| R5 | Stable identity and revisions | Deterministic manifest for identical content | Provider/account namespaces, logical identities, revision history |
| R6 | Catalog and search | Product contract and synthetic expected inventory | Searchable catalog and useful browsing experience |
| R7 | Portable packaging | Versioned directory snapshot and integrity manifest | Complete product package, readable catalog, optional transport container |
| R8 | Recovery and integrity | Local verification and separate-destination recovery | Destination-provider integrity verification and larger recovery corpus |
| R9 | Resumable work | Failed operations do not count as success | Durable checkpoints, cancellation, bounded adapter retries, restart protocol |
| R10 | Data handling and release readiness | Draft policies, local processing boundaries, synthetic examples | Counsel-reviewed notices, final retention rules, distribution approval |
| R11 | Explicit consent | Required acceptance and operation-scope design | Deployment-specific consent persistence, withdrawal and version migration |
| R12 | Engineering discipline | Golden Coding Standard and performance methodology | Ongoing review evidence and release-specific gates |

## Required synthetic scenario

The initial fixture must contain two confirmed projects, one confirmed
standalone conversation, one unknown association, a branched message graph,
repeated captures, and one missing artifact reference. It must not contain a
real user's private conversation history.

Preserving the fixture's JSON as bytes is not equivalent to implementing its
semantics. Expected catalog behavior is a future parser contract.

## Preservation invariants

1. Source files remain unchanged.
2. A missing original is reported, never regenerated.
3. Unknown associations remain unknown until evidence resolves them.
4. Restore targets are separate destinations; existing data is not overwritten.
5. Integrity results state exactly what was checked.
6. Matching hashes do not prove authenticity or protect against an attacker who
   can replace both the content and the trusted manifest.
7. Acceptance is explicit and limited to the stated operation.
8. A declined or outdated acceptance prevents processing through the user entry
   point.

## Completion rule

A requirement is complete only when its behavior, tests, operating limits, and
user-visible claims agree. Roadmap items remain open until the required evidence
is recorded.
