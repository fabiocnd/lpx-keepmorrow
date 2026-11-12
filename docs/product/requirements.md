# Requirements and Delivery Status

**Version:** 0.3.0 development candidate
**Reviewed:** November 12, 2026

This matrix identifies implemented behavior and the evidence still needed for
its intended use. Synthetic validation, deployed operation, source compatibility,
and public release are distinct claims.

| ID | Requirement | Implemented behavior | Remaining acceptance evidence |
| --- | --- | --- | --- |
| R1 | Explicit intake | CLI-selected directories/ZIPs; consent-gated portal upload handles; bounded experimental parser and capture outcomes | Authorized representative real export; native ChatGPT file acquisition if added |
| R2 | Preserve originals and structure | Exact regular-file bytes, empty directories, raw ZIPs, supported graphs/branches, escaped derived views, unknown fields retained in originals | Evidence that additional real source shapes are interpreted correctly |
| R3 | Available artifacts | Preserve supplied images and arbitrary binaries; bind explicit supported relative paths; report missing, unresolved, external, unsupported, and deliberately excluded references | Broader bindings supported by real export evidence; no claim about absent originals |
| R4 | Evidence-based association | Three distinct association states; reasons and decision history in immutable generations; authenticated reviewed service plans | Actual end-user usability and broader source association evidence |
| R5 | Stable identity and revisions | Provider/account/source identity, complete-record revision hashing, capture occurrences, immutable prior generations | Real-export identity continuity; physical deduplication only after a separate storage contract |
| R6 | Catalog and search | Bounded browsing, literal search, revision reading, standalone HTML, portal, and MCP Apps companion | Actual ChatGPT connection and host usability; larger representative workloads |
| R7 | Portable packaging | Versioned directory collections and bounded portable ZIPs; exact manifest retention; verified upload/download/unpack round trip | Selected deployment transport and storage-provider integration if required |
| R8 | Recovery and integrity | Separate new destinations; full restore and selected recovery; independent archive/catalog checks; explicit derivative omissions | Representative recovery corpus, host disaster recovery, and any future remote destination verification |
| R9 | Recoverable operations | Durable plans/reviews/jobs, idempotency, bounded worker ownership, cooperative cancellation, publication fencing, process-restart reconciliation, owned scratch cleanup | Payload power-loss durability, per-file resume, and deployment backup/restore drills |
| R10 | Data handling and release | Draft.3 notices; local operator and OAuth modes; bounded temporary retention; sanitized errors; documented private pilot limits | Actual host/region/operator, production retention policy, qualified legal review, selected source license, and public release decision |
| R11 | Explicit human consent | Exact CLI declarations; authenticated portal decisions with document digests, CSRF, single-use challenges, scoped grants, withdrawal, and separate exact-plan review | Live identity-provider flow, actual host behavior, and approved final legal presentation |
| R12 | Engineering discipline | Typed boundaries, Golden Coding Standard, adversarial fixtures, cross-record validation, reproducible assets, CI, measured synthetic workloads | Review of each changed contract; inspect final CI before any release claim |
| R13 | Distribution privacy | Source release preparation excludes private conversation records, biographical research, credentials, and operational user archives | Inspect the exact distributable and publication history; select a fresh public history or complete a separate history review |

## Preservation and authorization invariants

1. Sources and previous generations remain unchanged. Full imports retain the
   actual supplied originals, including compatible raw ZIP containers.
2. Unavailable material is reported. Source text and URLs never authorize remote
   fetching, execution, identity changes, or broader access.
3. Unknown association remains distinct from confirmed standalone status.
4. Every output uses a separate new destination with no replacement publication.
5. Selected recovery is a derivative with declared exclusions. Its intact binary
   attachments may contain additional information; selection is not redaction.
6. Integrity, interpretation, account coverage, and native restoration are
   different outcomes. A verified partial result remains partial.
7. Hashes establish consistency with the trusted manifest, not authenticity or
   protection from an attacker able to replace both data and manifest.
8. Authenticate and authorize before selected-content I/O. No model-callable tool
   creates human acceptance or approves an operation plan.
9. Active plans retain their exact grant/version/receipt. Completed descendants
   require current authorization for their own generation and every required
   ancestor scope. Renewal requires an explicit human decision on that ancestor.
10. Models remain outside authoritative identity, preservation, integrity,
    packaging, publication, and recovery decisions.

## Operating constraints

The service uses one process, one exclusive worker, and one content-I/O slot on
an operator-controlled local filesystem. Metadata status and cancellation do not
need that content slot. SQLite transactions coordinate grants and publication;
they do not make filesystem payload publication power-loss durable.

New generations copy retained captures. Queries verify full archive bytes before
reading bounded catalogs. Streaming buffers bound file I/O, while JSON and
semantic metadata are materialized under separate ceilings. No constant overall
memory, unlimited capacity, or provider synchronization is promised.

Default service limits include 128 MiB per upload, 512 MiB collection payload,
1 GiB encoded/expanded portable-package ceilings, 2 GiB per operation reservation,
and a 4 GiB managed logical storage budget. Configuration must cover the complete
upload pool plus one operation reservation. See the
[runbook](../operations/private-service-runbook.md) for exact bounds and retention.

## Completion rule

A requirement closes only when behavior, evidence, operating limits, and public
claims agree. Read [private pilot validation](../engineering/private-pilot-validation.md),
[import contract](../architecture/import-contract.md), and the
[delivery plan](../architecture/chatgpt-delivery-plan.md) before widening a claim.
