# Security and Data Handling

**Applies to:** The private 0.3.0 reference implementation

**Review date:** 2026-11-12

## Contact

Report a security concern to **fabio@lopixneural.com**, the project contact
designated by Fabio de Sousa Lopes. Include the affected version or commit,
reproduction steps using synthetic data, expected behavior, and observed impact.
Do not send passwords, access tokens, private conversation exports, or unrelated
personal information. No response-time or remediation SLA is promised.

Lopix Neural Inc. maintains LPX Keepmorrow. This repository is private and
proprietary under the current license. The owner plans an open-source transition;
the release license has not yet been selected or adopted, and visibility has
not changed. No public bug bounty is currently operated.

## Current implementation and evidence

Version 0.3.0 includes the deterministic preservation core, an optional private
service, a trusted human portal, an authenticated MCP reference integration,
durable operation metadata, and bounded binary transfer. Local operator mode
uses one explicit local identity and binds its socket to loopback. OAuth mode
adds a configured issuer/audience boundary and still requires a separately
selected authenticated HTTPS transport. A local operator key never enables
remote MCP access.

These implemented controls are exercised with synthetic fixtures. The
[private pilot validation record](docs/engineering/private-pilot-validation.md)
identifies executed checks and the remaining live identity-provider, ChatGPT,
representative-export, browser, and deployment gates. Local SDK or HTTP tests
do not establish that the user's account has been connected or approved.

| Boundary | Implemented behavior and material limit |
| --- | --- |
| Principal identity | Access binds the exact credential issuer and subject. Email addresses, source-account labels, and model arguments do not establish identity. |
| Human authorization | Current policy versions and document digests, selected actions, exact generations, and authenticated human receipts are checked. A model cannot create the receipt or review record through a tool. |
| Active operation scope | Canonical plans bind input digests, parameters, grant/version, and acceptance receipt. Fresh access is checked before I/O and before publication. |
| Derived resource disclosure | Applicable ancestor resource/generation/action permissions are checked. A fresh explicit human grant may renew a completed ancestor; a child grant alone cannot bypass it. |
| Untrusted inputs | ZIP structure, expansion, paths, links, duplicate identities, JSON budgets, catalog relationships, and actual bytes are validated against declared contracts. Source instructions and URLs remain inert. |
| Publication | Verified outputs use no-replacement publication. The authorization decision shares the same SQLite transaction as the grant check; the exclusive worker remains fenced through publication. |
| Restart and cleanup | An authorized output is independently verified before reconciled success. Scratch removal requires an exact journal record and matching ownership marker. Ambiguity retains capacity and requires review. |
| Intake and delivery | Ownership, byte ceilings, expiration, and active upload pins are enforced. Delivery has separate authorization and remains distinct from local verification. Already delivered bytes cannot be recalled. |
| Browser-facing content | The trusted portal and MCP component use bounded contracts and controlled rendering. Imported HTML, SVG, scripts, and executables are not activated as privileged previews. Visual/live-host validation is tracked separately. |

Source stability checks assume stable, operator-controlled directory ancestors.
They do not create a filesystem snapshot or defend against every hostile local
filesystem actor. SQLite journaling and atomic rename do not establish payload
power-loss durability. Multi-host operation, expiring worker leases, and
network-filesystem lock semantics are outside this reference contract.

## Privacy, credentials, and retention

Keep credentials outside source control, fixtures, model context, archives,
URLs, and logs. Local initialization creates an owner-only operator-key file on
POSIX; the operator must maintain appropriate Windows access controls. Do not
paste the key into a ChatGPT conversation or use it as a remote service token.
Keep dependency, certificate, and identity-provider configuration under operator
control; source content cannot select a provider or fetch destination.

Operational records use identifiers, counts, timestamps, digests, and bounded
error categories. The operation journal excludes conversation bodies, tokens,
and filesystem destinations. Necessary bounded parameters, including account
namespaces, project identifiers, and association reasons, are still retained
metadata and may be sensitive. Operation status excludes those text fields.
Diagnostics must not expose private paths or exception causes to clients or
general operational logs.

Uploads and service-owned delivery packages have explicit expiration and
cleanup rules. Persistent collection generations, historical plans, acceptance
receipts, reviews, and job metadata are not automatically purged. Source archives
are never selected by service retention cleanup. Revocation blocks new access;
it does not promise recall of delivered copies or secure erasure of every
retained byte. Declare the actual metadata, output, and backup retention policy
before processing real customer material.

See the [private service runbook](docs/operations/private-service-runbook.md),
[operation journal](docs/architecture/operation-journal.md),
[access contract](docs/architecture/access-control.md), and
[transfer contract](docs/architecture/transfer-contract.md) for the exact
ownership and failure boundaries.

## Handling a discovered defect

Preserve a minimal reproduction and record the affected commit. For a suspected
data-integrity defect, avoid further writes to the affected archive and retain
the available evidence. Do not claim earlier captures are valid until the
relevant checks have been repeated. Any repair must preserve the original
evidence and make resulting changes explicit.

If a credential was exposed, treat removing it from the latest file as
insufficient: the responsible owner should revoke or rotate it using the
provider's supported process. Coordinate any history rewrite because it changes
shared repository history.

## External integrations and AI

Before enabling an external service, document the destination, authorized scope,
data sent, retention assumptions, deletion behavior, and failure modes. Model
processing must follow the [AI Engineering Standard](docs/ai/ai-engineering-standard.md).
An archive import does not implicitly authorize training on its contents or
transmitting it to a model provider.

The current Keepmorrow implementation does not call a model for inference,
embeddings, training, hashing, identity decisions, or integrity verification.
Exposing deterministic tools to ChatGPT does not delegate authorization to the
host model. Future model-assisted features require their own reviewed data
scope and evaluation evidence.

Portable checksums support integrity checking; they do not by themselves prove
authorship, confidentiality, or the completeness of an upstream account. Report
only the guarantee actually established.
