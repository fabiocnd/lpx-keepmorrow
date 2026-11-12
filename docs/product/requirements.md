# Requirements and Delivery Status

This matrix carries forward the ten requirements in the
[Blueprint v0.2](../provenance/blueprint-v0.2-snapshot.md), with explicit consent
and engineering requirements added from the owner's instructions. It describes
internal version **0.2.0**. An implemented local capability does not close broader
compatibility, deployment, or release requirements.

| ID | Requirement | Implemented in 0.2.0 | Remaining acceptance evidence |
| --- | --- | --- | --- |
| R1 | Explicit intake | Selected directories and bounded stored/deflated ZIP intake; experimental mapping parser; capture provenance, parser version, per-document and item outcomes | Representative authorized real-export validation; additional supported source profiles and archive variants |
| R2 | Preserve originals and structure | Exact regular-file bytes, empty directories, and original ZIPs; validated message graphs, branches, null-message roots, and escaped derived views; unknown fields retained in originals | Authentic-source evidence that the supported graph and content interpretation matches actual exports; broader content forms |
| R3 | Available artifacts | All supplied regular files retained, including images and arbitrary binaries; explicit relative-path binding; stored, missing, unresolved, external, and unsupported states | Broader evidence-based attachment mappings and coverage across real export formats; no promise of unsupplied originals |
| R4 | Evidence-based association | Three validated states; source project evidence; explicit operator corrections with reasons and history in new generations | Authenticated actor attribution and user review in the eventual interface; broader source association evidence |
| R5 | Stable identity and revisions | Provider/account namespaces and source IDs; complete-record revision hashing; repeated capture occurrences; immutable previous generations | Real-export identity continuity evidence; durable storage design if physical deduplication or synchronization is added |
| R6 | Catalog and search | Paginated catalog/read commands; bounded literal search across revisions; standalone HTML; optional read-only MCP tools | Usability validation; authenticated ChatGPT connection; measured indexing requirements for larger collections |
| R7 | Portable packaging | Versioned collection, coverage report, standalone HTML, preserved captures, and SHA-256 manifest in an ordinary directory | Additional transport packaging and storage adapters; deployment-specific portability and durability evidence |
| R8 | Recovery and integrity | Full payload restore and selected conversation/project recovery to new destinations; archive and catalog validation; selected packages exclude recognized whole conversation exports | Larger authorized recovery corpus; remote destination integrity verification; any native-provider restoration would be a separate capability |
| R9 | Resumable work | Bounded processing, cancellation handling, staging cleanup, and publication after independent verification | Durable checkpoints, `fsync` durability design, abrupt-failure recovery, adapter retries, and restart/resume protocol |
| R10 | Data handling and release readiness | Draft policies, explicit local boundaries, synthetic examples, and loopback-only development adapter | Counsel-reviewed notices; authenticated hosting and retention/deletion rules; dependency review and distribution approval |
| R11 | Explicit consent | Exact current terms/privacy declarations required before selected-content inspection through CLI and MCP boundaries | Authenticated consent records, withdrawal, version migration, and disclosures for the chosen deployment |
| R12 | Engineering discipline | Golden Coding Standard, bounded contracts, adversarial fixtures, persisted-format validation, and recorded performance methodology | Continued review and release-specific gates; performance claims supported by comparable measured workloads |

## Compatibility and evidence status

The semantic adapter implements the exact experimental profile in the
[import contract](../architecture/import-contract.md). No representative real
ChatGPT account export has been validated. A `complete` parser result describes
supplied records within that profile; it does not establish complete account
history, complete attachment delivery, or compatibility with other source shapes.
An unavailable source-document record count remains `null` rather than being
reported as zero.

The original `examples/synthetic-input/catalog.json` remains an opaque
generic-archive demonstration. Preserving that file's bytes does not interpret
its conversation semantics. The new paired mapping exports in
`tests/fixtures/chatgpt_exports.py` exercise semantic collection behavior: two
source-confirmed projects, initially unknown associations, an explicit operator
decision establishing standalone status, renamed and repeated records, branches,
structural roots, and available or unavailable artifacts. Fixtures contain
synthetic conversation content and binary test data.

The optional loopback MCP adapter is exercised through the official SDK. It is
not installed in a ChatGPT account, deployed to a reachable service, or equipped
with end-user authentication. Protocol validation and actual ChatGPT acceptance
testing are separate gates. The [ChatGPT integration contract](../architecture/chatgpt-integration.md)
records those boundaries; [collection verification](../engineering/collection-verification.md)
records observed validation commands and results.

## Preservation invariants

1. Source files and previous generations remain unchanged. Full import generations
   retain supplied originals, including raw ZIP containers when applicable.
2. A missing original is reported, never regenerated. Imported URLs and content
   do not authorize remote fetching or execution.
3. Unknown associations remain unknown until evidence or an explicit operator
   decision resolves them. Missing project metadata does not prove standalone status.
4. Writes and restores use separate new destinations; existing data is not overwritten.
5. Selected recovery is a derivative with declared exclusions. Full originals stay
   in its parent collection; arbitrary chosen attachments are not internally redacted.
6. Integrity and coverage results state exactly what was checked. A verified
   partial collection remains partial, and no result implies native ChatGPT restoration.
7. Matching hashes do not prove authenticity or protect against an attacker who
   can replace both the content and the trusted manifest.
8. Acceptance is explicit and limited to the stated operation. A missing or
   outdated declaration prevents selected-content processing through user entry points.
9. Models do not decide authoritative identity, integrity, preservation, or recovery.

## Operating constraints

New generations physically copy retained captures. Logical revision reuse does
not provide physical blob deduplication. Queries verify the whole archive before
scanning the catalog. JSON and retained metadata have explicit resource ceilings;
the implementation does not promise constant memory or unrestricted archive sizes.
Atomic publication does not establish crash durability or resumable execution.

The [local collection workflow](../architecture/collection-workflow.md) describes
commands, acceptance, package layout, and result codes. A verified partial or
unsupported collection uses exit status `3`; successful selected recovery also
uses `3` because selection is intentionally incomplete. Consumers must inspect
the structured result before deciding whether an output was produced.

## Completion rule

A requirement is complete only when its behavior, tests, operating limits, and
user-visible claims agree. Roadmap items remain open until the required evidence
is recorded. Synthetic tests, SDK protocol tests, and local integrity checks
cannot substitute for authentic-source compatibility, authenticated deployment,
retention policy, or legal approval.
