# Engineering and Distribution Decisions

**Reviewed:** November 12, 2026
**Version:** 0.3.0 development candidate

This register records product and engineering decisions, their consequences, and
remaining release choices. Private development conversations and personal research
are outside the distributable documentation. Status is implementation evidence,
not a substitute for operational or legal acceptance.

| ID | Decision | Status | Rationale and consequence |
| --- | --- | --- | --- |
| D001 | Use LPX Keepmorrow and `lpx-keepmorrow` | Adopted | Stable product and package identity |
| D002 | Author code, documentation, comments, and UI in US English | Adopted | One maintained technical vocabulary; original imported bytes retain their language |
| D003 | Keep the maintained product free and nonmonetized | Product direction | Separate from downstream rights under a future open-source license |
| D004 | Attribute Lopix Neural Inc. and Fabio de Sousa Lopes | Adopted | Proportionate professional attribution without modifying preserved originals |
| D005 | Preserve the private development history | Historical license superseded by D037 | Do not publish old refs, logs, or private development records |
| D006 | Use fabio@lopixneural.com as professional contact | Adopted | Consistent package, security, and maintainer contact |
| D007 | Apply the project Golden Coding Standard | Adopted | Typed boundaries, explicit invariants, meaningful tests, measured claims; no external certification implied |
| D008 | Group files by responsibility | Implemented | Cohesive domain, integration, documentation, and operational boundaries; ADR 0001 |
| D009 | Require acceptance before selected-content processing | Implemented | Explicit CLI declarations and authenticated portal decisions serve different trust boundaries |
| D010 | Keep legal limitations subject to applicable law | Draft policy | No absolute immunity, undisclosed retention authority, or waiver of mandatory rights |
| D011 | Keep the deterministic core on Python 3.11+ standard library | Implemented | Minimize authoritative runtime dependencies; HTTP/OAuth/MCP remain optional |
| D012 | Use a versioned directory archive with exact manifests | Implemented | Inspectable byte preservation, separate verification, and ordinary-file recovery |
| D013 | Keep model assistance outside preservation decisions | Implemented boundary | No model inference, training, authoritative identity, or integrity decisions |
| D014 | Maintain the existing repository namespace | Current state | Any public destination is selected with the distribution plan |
| D015 | Treat Google Drive as a possible later storage adapter | Deferred | No provider integration or reused credentials |
| D016 | Separate source publication from hosted-service launch | Adopted | A source license does not approve hosting, processing purposes, or retention |
| D017 | Select actual hosting, region, identity provider, and operational policy before live processing | Open | Configuration examples do not establish a live deployment |
| D018 | Exclude private development records from the distributable source tree | Adopted for release preparation | Preserve reusable product and engineering requirements without conversation snapshots or biographical research |
| D019 | Implement continuity, evidence, and selected recovery around supplied exports | Implemented | Native export remains the source acquisition mechanism |
| D020 | Use immutable collection generations | Implemented | Previous outputs remain unchanged; physical copy costs are explicit; ADR 0002 |
| D021 | Keep parser compatibility experimental | Current limit | Synthetic fixtures do not replace an authorized representative real export |
| D022 | Retain the legacy loopback read adapter for synthetic development | Implemented | Separate from the authenticated service; no production identity claim |
| D023 | Describe local collection processing in draft.2 policies | Superseded by D032 | Historical scope was expanded for the private service |
| D024 | Require actual ChatGPT and real-source acceptance evidence | Open gate | Backend and UI implementation can proceed before those external dependencies, but cannot close them |
| D025 | Record human acceptance and per-principal exact-generation grants | Implemented | Model arguments cannot manufacture assent; active plans bind exact receipts |
| D026 | Review content eligibility before connecting real material | Open gate | Neither private installation nor a checkbox establishes platform eligibility |
| D027 | Implement the private service as one process with one worker | Implemented | Bounded coordination and failure model; ADR 0003 |
| D028 | Share transactional SQLite state between grants and operations | Implemented | Serialize publication authorization against revocation using the same immediate transaction |
| D029 | Separate trusted human decisions from model-callable tools | Implemented | Browser sessions, CSRF, exact snapshots, single-use challenges, and independent plan review |
| D030 | Reconcile process stops and clean only proven owned scratch | Implemented | Exclusive worker epoch, intended output digest, ownership ledger/marker, and refusal of ambiguous cleanup |
| D031 | Use the portal for private-pilot file transfer | Implemented | Bounded upload and authorized download; native ChatGPT file acquisition remains separate work |
| D032 | Use policy version 2026-11-12-draft.3 for the current private service | Draft implementation policy | Accurate disclosure of service identity, consent, temporary storage, operations, and unresolved deployment choices |
| D033 | Keep active-plan fencing strict while allowing explicit completed-ancestor renewal | Implemented | Fresh child permission alone cannot override ancestor withdrawal; historical plans remain immutable |
| D034 | Validate storage budgets before startup | Implemented | Require the full upload pool plus one 2 GiB operation reservation; admission still checks retained outputs and free space |
| D035 | Prepare an open-source transition | License decision completed by D037 | Public repository creation remains a separately verified action |
| D036 | Publish only reviewed source with an appropriate history boundary | Release requirement | Deleting current files does not remove earlier commits, CI logs, or artifacts |

| D037 | Adopt Apache-2.0 for this source revision | Owner-authorized | Align root license, metadata, notices, and current guidance; exclude private records and user content |
| D038 | Publish a fresh source snapshot to `fabiocnd/keepmorrow` | Authorized destination; administrative execution pending | Preserve the LPX Keepmorrow product/package identity and keep `fabiocnd/lpx-keepmorrow` private |
| D039 | Advance terms to draft.4 and retain privacy draft.3 | Draft policy | Correct source-license disclosure without broadening processing permissions; require new acceptance |

## Change discipline

Record substantive architecture changes in a focused ADR. Update implementation
contracts, tests, operating limits, and user-facing claims together. Historical
technical measurements retain their original workload and version attribution.
Do not turn a synthetic test into a live deployment claim or a licensing proposal
into an effective source grant.
