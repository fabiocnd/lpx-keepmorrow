# Consent and Operation Boundary

**Owner:** Lopix Neural Inc.
**Contact:** fabio@lopixneural.com
**Status:** Implemented local and private-service boundaries; synthetic validation only
**Terms version:** `2026-11-12-draft.3`
**Privacy version:** `2026-11-12-draft.3`
**Review date:** 2026-11-12

LPX Keepmorrow separates agreement to the current documents, permission for a
specific resource and action, and approval of a prepared operation. A valid
credential or a model-supplied argument does not establish all three decisions.
The applicable boundary must authorize an operation before it inspects selected
content. Configuration loading and policy presentation do not inspect that
content.

The [Terms of Use](../../legal/terms-of-use.md),
[Privacy Notice](../../legal/privacy-notice.md), and
[Consent and Operation Authorization](../../legal/consent-and-operation-authorization.md)
remain internal drafts. Technical acceptance does not establish counsel approval,
legal enforceability, a live account connection, or permission to launch a public
service.

## Supported boundaries

| Boundary | Identity and acceptance contract | Supported use |
| --- | --- | --- |
| Ordinary CLI | Exact terms and privacy version flags for each content-processing invocation; no authenticated identity | Explicit local operations |
| Legacy MCP development adapter | Exact version arguments before resolving a configured opaque collection ID; no authenticated human acceptance | Synthetic loopback development only |
| Private browser portal | Authenticated session, exact Origin, CSRF validation, displayed scope, and single-use interaction challenge | Human consent, operation review, and controlled local or configured OAuth service use |
| Private MCP endpoint | Verified external access token, allowlisted issuer/subject identity, and existing current human-accepted grants | Requests within already accepted scopes; no acceptance or review tool |
| Internal Python APIs | Caller-owned trust boundary; constructing domain objects proves no identity or assent | Application implementation and isolated tests |

Local operator mode exposes the portal on loopback and has no MCP endpoint.
OAuth mode requires explicit provider and browser-client configuration. Its MCP
transport retains the SDK's complete authentication middleware. A browser cookie
does not authenticate MCP, and a bearer token alone does not authorize a human
consent submission. See [external authentication](external-authentication.md)
and the [trusted portal](trusted-portal.md).

## Local invocation contract

`keepmorrow.consent.require_acceptance(terms_version, privacy_version, operation)`
accepts exact current version strings and one of `create`, `verify`, `restore`,
`import`, `catalog`, `search`, `read`, `associate`, or `recover`. It performs no
file or network access. Missing, stale, malformed, or unsupported declarations
raise `ConsentError` before selected content is accessed.

The CLI requires both options after the operation name. It has no remembered
acceptance or implicit `latest` value:

```bash
PYTHONPATH=src python -m keepmorrow create examples/synthetic-input /tmp/keepmorrow-example \
  --accept-terms 2026-11-12-draft.3 \
  --accept-privacy 2026-11-12-draft.3
```

The operation and explicit paths define that invocation's scope. Its immutable
receipt contains the accepted document versions, UTC timestamp, and operation
name. The CLI returns it as `acceptance` in JSON output: stdout for ordinary
results, or stderr when an accepted operation fails. It contains no identity
proof, credentials, selected paths, or content. The application does not persist
this local receipt in a consent database; the caller controls any output capture.
Refused acceptance creates no receipt. A receipt is not evidence of successful
execution or verified recovery.

The legacy MCP adapter's version arguments establish only a client declaration.
They must never be promoted to authenticated consent in the private service or
used to expose the development adapter remotely.

## Private-service consent and review

The service derives a principal from verified identity or the explicitly
configured local operator. Email addresses, source account labels, and tool
arguments cannot select another principal. The access store records two distinct
objects: an administrative grant and a human acceptance of its selected action
subset. Creating a grant alone does not authorize content access.

Consent preparation presents the exact resource, immutable generation, actions,
purpose, recipient, policy versions and byte digests, and versioned content
eligibility declaration. Submission requires four deliberate choices: terms
agreement, privacy acknowledgment, scope authorization, and content eligibility.
The server checks the displayed snapshot and atomically consumes its challenge,
records acceptance, and retains the scope-digest and eligibility context. Replay,
changed policies, changed scope, and nonliteral Boolean declarations fail closed.
No model-callable tool can perform this interaction.

Import, association, recovery, package creation, and unpacking also require an
immutable prepared plan and a separate human review of its canonical parameter
digest. Starting consumes that review. Repeating the same principal-scoped
idempotency key identifies the same operation; it does not create another
capture. Upload permission is checked before intake and does not imply import
permission. A newly created collection or package needs its own accepted scope
before content delivery.

The service persists principal digests, exact scope and policy evidence, bounded
plan parameters, expiry, revocation, and operation state. It does not persist raw
OAuth tokens, browser cookies, or conversation bodies in the consent ledger.
These records provide technical evidence of the recorded interaction; they do
not prove that a person understood every provision or had authority over all
third-party information. The [access contract](access-control.md) defines the
internal APIs and transaction requirements.

## Current authority, renewal, and withdrawal

Every authorization checks current policy versions and exact document digests.
An old receipt cannot authorize changed policies. Action names are independent:
`read` does not imply `recover`, `package`, or `download`.

| Requested behavior | Required current authority |
| --- | --- |
| Admit, continue, or authorize publication of active work | The reviewed primary grant ID, version, and acceptance receipt for the exact resource, generation, and action, plus required ancestry and intake scopes |
| Disclose a completed or partially completed result | Current explicitly accepted permission for each completed ancestor's exact resource, generation, and action, plus the requested result's own access scope |
| Return completed-operation result metadata | Current authority for the creating plan's exact scope and its ancestry; otherwise output identifiers and results are withheld |
| Stream a package | The exact selected download grant, live browser session, available unexpired package, and authorized ancestry, rechecked before and after each frame read |

Fresh consent cannot replace an active plan's immutable primary grant or receipt.
If that authority ends, the owner must prepare and review new work. Completed
history is different: the owner may explicitly renew an ancestor through a new
grant and acceptance for its exact scope. That renewal restores eligible future
disclosure without rewriting historical plans, receipts, or preserved bytes.
A grant on a child collection alone cannot override an unauthorized ancestor.
Renewing permission also does not extend a package's separate access lifetime or
recreate bytes already removed by retention maintenance.

Publication authorization and revocation share one immediate SQLite transaction
boundary. Revocation committed first prevents authorization under that grant. If
the publication decision commits first, the verified private publication may
finish; subsequent delivery is independently authorized. Download checks stop
future frames after authorization loss or package expiry. Already transmitted
bytes cannot be recalled, and withdrawal does not silently delete completed
collections or change original source material.

## Scope and retained evidence

No current acceptance authorizes source deletion, overwrite, account enumeration,
model inference, training, advertising, or public redistribution. Original files
and previous immutable generations remain distinguishable from derived outputs.
Filesystem validation, integrity checks, storage admission, and no-overwrite
rules remain mandatory after acceptance.

Temporary uploads and download packages have separate bounded access and cleanup
rules. Completed collections and historical control records remain subject to
incident and retention procedures approved for the actual deployment. The
implementation does not provide automatic long-term consent-ledger purge or
secure erasure, and it cannot delete copies held by another recipient. Production
requires a documented retention schedule, actual operator and recipient
disclosures, and qualified legal review. See the
[Privacy Notice](../../legal/privacy-notice.md) for the current categories.

## Verification scope

Synthetic CLI tests establish version refusal before selected-data processing.
Access tests cover identity separation, current policy digests, replay, expiry,
revocation, and both transaction orderings against publication. Application
tests demonstrate that a child grant cannot bypass an expired ancestor, explicit
parent renewal restores completed-result access without changing history, and
fresh consent cannot rebind an uncompleted plan.

Portal tests cover authenticated cookies, Origin and CSRF checks, deliberate
choices, review separation, scoped uploads, and bounded verified downloads.
Streaming tests stop transmission after grant withdrawal or package expiry and
close resources on disconnect. Lifecycle tests refuse failed startup, suppress
private error details, and release worker ownership.

These are implementation checks with synthetic fixtures. They do not establish
a real identity-provider connection, ChatGPT account availability, production
capacity, legal approval, or enforceability of the draft agreement.
