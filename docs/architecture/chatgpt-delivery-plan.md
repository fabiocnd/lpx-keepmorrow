# ChatGPT Integration Delivery Plan and Status

**Version:** 0.3.0 development candidate
**Reviewed:** November 12, 2026
**Status:** Private-service implementation complete for the documented synthetic scope; live acceptance and public release remain open

## 1. Delivery objective

Allow an authorized person to inspect explicitly selected conversation collections
and review preservation or recovery work through a trusted service and ChatGPT
interface. Preserve exact supplied bytes, report interpretation gaps, and prevent
model arguments from manufacturing human consent or broader object access.

The deterministic core, authenticated service, human portal, durable operations,
portable transfers, and MCP Apps companion are implemented. This record separates
that work from a real account connection, authentic-source compatibility, selected
hosting, and approved release conditions.

The [requirements](../product/requirements.md), [system overview](system-overview.md),
and [private pilot validation](../engineering/private-pilot-validation.md) define
the current contract and observed evidence. The original 0.2.0 loopback adapter
remains a separate synthetic development surface.

## 2. Phase status

| Phase | Implemented work | Evidence still required to close the phase |
| --- | --- | --- |
| P0 — Scope and platform | Explicit selected-input model, content eligibility gate, identity/host configuration, current documentation; authenticated account exposes custom MCP creation | Running endpoint and completed account connection, permitted content, host/operator/region, provider and cost decisions |
| P1 — Actual ChatGPT connection | Official SDK tool server, resource metadata, bounded responses, MCP Apps resource, protocol tests | Installation and invocation in the intended signed-in ChatGPT account; reconnect and permission behavior |
| P2 — Real-export compatibility | Experimental parser, provenance, coverage reports, synthetic graphs/binaries/revisions | An authorized representative export and independently reconciled coverage expectations |
| P3 — Authenticated pilot | JWT resource validation, principal allowlist, exact grants, human consent, withdrawal, CSRF, generation and ancestor checks | Live IdP discovery/client registration, actual OAuth flow, eligible real collection, approved disclosures |
| P4 — Interface and transfer | Typed MCP Apps companion, trusted portal, explicit uploads, verified downloads, DOM and SDK tests | Actual ChatGPT host behavior, accessibility/usability qualification, selected transport; native file-picker acquisition if required |
| P5 — Durable operations | Canonical reviewed plans, idempotency, bounded worker, cancellation, publication fencing, process restart, owned cleanup, package/unpack | Deployment fault drills and any future per-file resume or power-loss contract |
| P6 — Operating release | Synthetic service benchmark, resource budgets, runbook, deployment examples, CI configuration, package verification | Selected-host measurements, backup/restore/incident drills, production retention, legal approval, final CI and release decision |

Engineering implementation proceeded where external account and hosting inputs
were unnecessary. An implemented component does not close an unmet live gate.
See the validation record for exact test counts, source digests, and CI status.

## 3. Adopted architecture

Retain the standard-library Python preservation core. Add cohesive packages for
access, transactional state, operations, transfers, application coordination, and
optional integration. Use one process, one exclusive worker, and local SQLite on
an operator-controlled filesystem. Use the official MCP Apps SDK for the compact
TypeScript companion. [S3][S4][S10]

| Boundary | Adopted behavior |
| --- | --- |
| Identity | Configured HTTPS issuer/JWKS, resource audience, access-token type, scope, client claim, explicit principal allowlist |
| Human decisions | Authenticated portal, short-lived session, CSRF, single-use scope challenge, exact policy digests, separate reviewed plan |
| Authorization | Resource and immutable generation, action, purpose, recipient, expiry, current acceptance, and required ancestors |
| Operations | Typed canonical plan, one deliberate review per new operation, scoped idempotency, bounded reservations and attempt ownership |
| Publication | Same-database immediate transaction orders authorization against revocation; filesystem output publishes without replacement |
| Recovery | Exclusive startup reconciliation verifies expected outputs; cleanup requires proven workspace ownership |
| Transfer | Authorized bounded upload handles and portable ZIPs; no arbitrary source-URL downloader |
| Interface | One rendering tool with an MCP Apps resource; data tools return bounded structured results |

[ADR 0003](decisions/0003-private-preservation-service.md) records the tradeoffs.
No broker, distributed worker fleet, vector database, or model runtime is needed
for the implemented pilot.

## 4. Human acceptance and lineage

Account linking, policy acceptance, processing scope, and exact operation review
are separate decisions. The consent preparation view displays the current
version and digest of each policy, resource/generation, actions, purpose,
recipient, and eligibility declaration. The service enforces grant expiration,
but the preparation response does not currently include its timestamp; that
presentation gap remains part of live consent qualification. No checkbox is
preselected. No MCP tool can record acceptance or approve a plan.

An active operation remains bound to its exact reviewed grant/version/receipt.
A completed generation can remain accessible after an earlier scope expires only
when fresh explicit acceptance authorizes every required ancestor scope as well
as the child. A new child or download grant alone cannot restore a withdrawn
ancestor. Historical plans and original bytes are unchanged by renewal.

Revocation committed before publication authorization prevents that decision.
A prior committed publication decision may finish privately, while later access
and delivery still require current authorization. Already transmitted bytes cannot
be recalled. These are engineering controls; approved legal applicability and
consent presentation remain separate obligations. [S8][S9]

See [access control](access-control.md), [trusted portal](trusted-portal.md),
[consent boundary](consent-boundary.md), and [operation journal](operation-journal.md).

## 5. Implemented MCP and portal contracts

| Surface | Implemented contracts | Purpose |
| --- | --- | --- |
| MCP metadata/UI | `access_status`, `render_keepmorrow`, `list_collections` | Inspect authorized scope and open the companion without automatic content processing |
| MCP reads | `browse_collection`, `search_collection`, `read_revision`, `verify_collection` | Bounded explicit reads of an authorized exact generation |
| MCP planning | `prepare_import`, `prepare_recovery`, `prepare_association`, `prepare_package`, `prepare_unpack` | Persist typed intent under prior processing authorization |
| MCP operation control | `start_operation`, `get_operation`, `list_operations`, `cancel_operation` | Require human-reviewed intent for a new start; inspect and cancel owned work |
| Trusted portal | Scope acceptance/withdrawal and exact-plan review | Record deliberate human actions independently of model calls |
| Portal transfer | Bounded upload and verified download | Keep binary bodies outside MCP JSON and recheck delivery access |

The service uses 64 KiB MCP request and 512 KiB result envelopes. Paths never come
from model-supplied arguments. Source account labels remain provenance. Unknown
or unavailable artifacts are reported rather than fetched or invented.

Portal file transfer is the implemented pilot path. Native ChatGPT file-selection
APIs are a separate capability decision and have not been integrated. The actual
host bridge and any transport constraints must be verified in the selected account.
The UI uses the shared MCP Apps contract and official SDK. [S4][S5][S6]

## 6. Operations, resource bounds, and retention

Plans are immutable and content-independent metadata records. Their digests bind
principal, parameters, input digest, exact scope, and reservation. One deliberate
review authorizes one new operation. Replaying the same key and canonical intent
returns the existing operation; changing intent under that key fails.

The exclusive worker holds its OS lock during live executor work. Terminal
status can precede cleanup and reservation release. A failure classified as
`OperationCleanupRequired` retains the reservation and stops new claims; the
[operation protocol](operation-journal.md) explains the separate metadata-error
boundary. Cancellation is cooperative. Metadata status/cancellation remain
outside the heavy-content slot. Startup recovers proven owned scratch and upload
pins, reconciles publication, and only then performs retention cleanup.

Default limits include 128 MiB uploads, a 512 MiB collection payload, independent
1 GiB encoded/expanded package ceilings, a 2 GiB job reservation, and 4 GiB managed
logical storage. Configuration must reserve the entire upload pool plus at least
one job. Retained generations count against subsequent admission. Logical bounds
are not filesystem quotas or throughput guarantees.

Upload lifetime is at most one hour or the configured shorter retention period.
Delivery packages expire after the configured period, by default 24 hours from
operation creation. Completed collections and historical control metadata remain
retained until an explicit operator procedure; automated long-term metadata
purging is not implemented. Current access is checked during streaming. Exact
retention and backup rules for a hosted service still require a selected operator.

The [runbook](../operations/private-service-runbook.md) covers startup, configuration,
backup, cleanup ambiguity, incidents, and rollback. The
[benchmark](../../benchmarks/PRIVATE_SERVICE_BENCHMARK.md) measures one synthetic
local service workflow and does not establish HTTP, IdP, tunnel, or ChatGPT latency.

## 7. External acceptance work

| Work item | Completion evidence | Current blocker or decision |
| --- | --- | --- |
| Actual account connection | Discover tools, open UI, perform an authorized query, reject unsupported scope, and recover from interruption in ChatGPT | Authenticated custom-MCP creation form verified; a running endpoint and live OAuth are still required before creation and installation |
| Representative export | Inventory and graph expectations reconcile; byte hashes and unsupported cases are recorded | Explicitly supplied authorized sample; no user archive is committed to source |
| Live OAuth | Issuer metadata, clients/callbacks, resource audience, token rotation, wrong-user rejection, and browser flow pass | Selected IdP and registered clients |
| Reachable service | Configured authentication survives the selected proxy or tunnel; limits and timeouts are observed | Host/operator/region or supported private tunnel |
| Real content eligibility | Reviewed selection and all reachable derivatives satisfy applicable platform requirements | Actual content and policy review; private installation is not an exemption |
| Operating qualification | Backup/restore, revocation, capacity, incident response, and rollback evidence on the selected host | Running deployment and approved operating procedures |
| Legal release | Approved final terms, privacy notices, retention, and support obligations | Owner and qualified counsel review |
| Open-source release | Exact license, current dependency notices, sanitized source artifact, and reviewed publication history | License adoption and public destination decision |

The authenticated ChatGPT account exposed the custom-MCP creation form on
November 12, 2026. A local form draft contains the product name, description,
and OAuth selection; no server URL or tunnel identity has been provisioned, and
the plugin has not been created or installed. No account identifier or browser
session evidence is retained in source. The full signed-in acceptance flow
remains open. Local DOM/protocol tests and successful synthetic Chromium CI are
separate from that live gate. No credentials are requested through chat or
stored in source.

## 8. Connectivity and product policy

A supported secure MCP tunnel is a private-pilot candidate; authenticated HTTPS
is another candidate. A tunnel changes reachability, not caller identity or
object authorization. Its setup, current limits, and authorization-server path
must be checked in the selected environment. Public distribution and hosted
service availability have their own requirements. [S1][S2][S6]

Arbitrary conversation exports can contain information outside permitted plugin
processing. Keep original preservation under the operator's controlled scope and
review eligible connected selections. A derivative must declare its parent and
omissions. Source JSON, ZIPs, artifacts, metadata, and errors must not bypass that
boundary. A checkbox or automated sanitizer is not a platform exemption. [S7][S11]

## 9. Release discipline

Keep platform capabilities, implemented code, measured results, and unresolved
decisions separately identifiable. Record exact release source, configuration,
test inputs, observed outcomes, and limits. Recheck changing official requirements
before live connection. Public source licensing does not publish user archives,
authorize hosted processing, or establish a native restoration capability.

The next deployment work should start from the concrete validated package and
configuration examples, then resolve the account/IdP/host gates above. Additional
engineering is driven by observed failures or a specified capability, rather than
by completing speculative infrastructure.

## 10. Primary source register


Reviewed on November 12, 2026. Recheck changing platform requirements when the
associated phase is implemented. Platform facts are distinguished above from
proposed engineering decisions and unresolved owner/legal choices.

| ID | Source | Planning use |
| --- | --- | --- |
| S1 | [OpenAI: Add custom MCP server](https://developers.openai.com/api/docs/guides/custom-mcp-server) | Actual account connection and permissions |
| S2 | [OpenAI: Secure MCP Tunnel](https://developers.openai.com/api/docs/guides/secure-mcp-tunnels) | Private connectivity, constraints, and public-distribution boundary |
| S3 | [OpenAI: Authentication](https://developers.openai.com/plugins/build/auth) | Supported identity integration |
| S4 | [OpenAI: Add UI to your MCP server](https://developers.openai.com/plugins/build/chatgpt-ui) | Shared UI bridge and optional host capabilities |
| S5 | [OpenAI: Plugin reference](https://developers.openai.com/plugins/reference) | File-selection and file-parameter contracts |
| S6 | [OpenAI: Connect and test your plugin](https://developers.openai.com/plugins/deploy/connect-chatgpt) | Actual conversation and UI evaluation |
| S7 | [OpenAI: Plugin guidelines](https://developers.openai.com/plugins/plugin-guidelines) | Content eligibility and disclosure requirements |
| S8 | [OPC: Meaningful consent](https://www.priv.gc.ca/en/privacy-topics/privacy-for-businesses/appropriate-handling-of-personal-information/collecting-personal-information-and-consent/consent/gl_omc_201805/) | Understandable decisions and processing scope |
| S9 | [OPC: Limiting use, disclosure, and retention](https://www.priv.gc.ca/en/privacy-topics/privacy-laws-in-canada/the-personal-information-protection-and-electronic-documents-act-pipeda/p_principle/principles/p_use/) | Purpose-based retention and disposal design |
| S10 | [MCP: Authorization specification](https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization) | Resource authorization contract |
| S11 | [OpenAI: Security and privacy](https://developers.openai.com/plugins/guides/security-privacy) | Server enforcement and data minimization |
| S12 | [OpenAI: Package your plugin](https://developers.openai.com/plugins/build/plugins) | Packaging after integration validation |


Related documents: [system overview](system-overview.md),
[private pilot validation](../engineering/private-pilot-validation.md),
[roadmap](../product/roadmap.md), [decision register](../governance/decision-register.md),
and [open-source transition](../governance/open-source-transition.md).
