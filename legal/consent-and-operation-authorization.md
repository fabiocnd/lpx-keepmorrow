# Consent and Operation Authorization

**DRAFT FOR OWNER AND QUALIFIED ONTARIO COUNSEL REVIEW**
**Document version:** `2026-11-12-draft.4`
**Prepared:** 2026-11-12
**Production approval:** Not granted by this document

This document defines the internal consent-control behavior and proposed
production interaction. It does not certify the enforceability of the draft
[Terms of Use](terms-of-use.md) or [Privacy Notice](privacy-notice.md).

## 1. Separate the Decisions

| Decision | Meaning | Current implementation status |
| --- | --- | --- |
| Accept the stated Terms version | Deliberate agreement to the presented document, subject to mandatory law | Required CLI version flag or separate unchecked portal control; draft documents only. |
| Acknowledge the Privacy Notice and authorize necessary processing | Understanding of the described handling and authorization for the selected action | Required CLI version flag or separate portal privacy and scope controls; no optional processing is bundled. |
| Confirm content eligibility | Declare that the selected material satisfies the displayed connected-use restrictions | Separate unchecked portal control, recorded with the versioned eligibility declaration. |
| Request a local operation | Select `create`, `verify`, `restore`, `import`, `catalog`, `search`, `read`, `associate`, or `recover` with its declared scope | Explicit CLI command and arguments; legacy development MCP read tools use configured collection IDs. |
| Review private-service work | Confirm the immutable parameters of an import, association, recovery, package, or unpack operation | Separate authenticated human review of a prepared plan; starting consumes that review. |
| Authorize private service transfer | Approve a specified recipient, purpose, data selection, and consequences | Authenticated portal scope; actual deployment and recipient review remain release gates. |
| Authorize model inference or training | Approve a separately described model purpose and provider | Unavailable; neither inference nor training is implemented. |
| Authorize a destructive source action | Approve named objects and a specific deletion, overwrite, move, or mutation | Unavailable; no current source-deletion operation. |

Agreement to terms is not itself authorization for every possible use of data.
Document acceptance and operation authorization must both exist before accessing
the selected material. Do not infer either from silence, a preselected checkbox,
the mere presence of files, a previous operation, or continuation after an error.

## 2. Current CLI Gate

Each operation requires these exact values:

```text
--accept-terms 2026-11-12-draft.4
--accept-privacy 2026-11-12-draft.3
```

The caller must be able to read the two versioned documents before supplying the
flags. Missing, outdated, or mismatched acceptance prevents the archive service
from inspecting or processing the selected data. Help and legal-document access
must remain available without accepting an operation.

For an internal synthetic-data evaluation, an explicit command takes this form:

```bash
python -m keepmorrow create ./synthetic-source ./new-archive \
  --accept-terms 2026-11-12-draft.4 \
  --accept-privacy 2026-11-12-draft.3
```

The source, destination, and operation arguments specify the current invocation.
The flags must not be silently inserted by an end-user wrapper or derived from
an unrelated approval. A scheduled job would need a separately reviewed
authorization describing its recurring scope, duration, and revocation behavior;
these per-invocation flags do not supply that production workflow.

The CLI is the local user boundary. The optional MCP development read tools
likewise require exact document versions before resolving or inspecting a
configured collection. They accept opaque collection IDs, not arbitrary paths.
These declarations do not authenticate an end user or prove that a person, rather
than a calling client, supplied them. Internal Python functions remain engineering
interfaces. The separate private service supplies an authenticated portal and persisted
human acceptance. The legacy declarations never become that service's identity
or consent evidence. Real hosting and ChatGPT account connection remain
separately verified release gates.

## 3. What the Local Receipt Establishes

The reference CLI returns acceptance metadata containing the accepted Terms
version, accepted Privacy Notice version, a UTC acceptance time, and the operation
name. This metadata records the invocation's stated acceptance. It is local and
contains no identity proof, signature, raw content, or automatic server record.

The receipt does not establish that a person read or understood the documents,
that the caller was authorized to act for another person, that counsel approved
the text, or that processing succeeded. The operation result must establish
completion separately. The acceptance metadata alone is not a full record of
the selected file paths or inventory.

The private service separately stores the exact issuer/subject-derived principal,
policy versions and byte digests, resource generation, permitted actions,
purpose, recipient, deliberate interaction ID, expiry, and revocation. The
recording boundary requires an authenticated browser session, exact Origin,
CSRF validation, and a single-use challenge bound to the displayed scope. The
acceptance transaction consumes that challenge and writes the receipt together.
No MCP tool creates acceptance or operation review.

The service stores bounded plan parameters and control metadata, including
source labels and association reasons when necessary. It must not copy
conversation bodies or raw tokens into these records. The private service's
long-term metadata purge policy remains a production release requirement; see
the Privacy Notice and operating runbook.

## 4. Implemented Private Portal Presentation

Present the product's actual operator and both documents near the decision. Show
the requested action and selected source and destination before the user confirms
processing. Use accessible, separately selectable controls with no preselection.

Agreement control:

> I have had the opportunity to read and agree to the LPX Keepmorrow Terms of Use
> shown here, version [displayed version].

Privacy and necessary-processing control:

> I have reviewed the Privacy Notice, version [displayed version], and authorize
> the necessary local processing of the selected material for the operation
> shown here.

Operation confirmation:

> I authorize [displayed operation] using [selected source] and, where applicable,
> [selected destination]. This creates or checks the described local files. It
> does not authorize deletion or alteration of the original source.

Explain near these controls that private information may appear in archive
contents and filenames, that output copies remain under the user's storage
settings, and that recovery covers supplied supported material. Native project
structure and unavailable source relationships may not be reconstructable.
Make clear that backups and restore checks remain necessary.

Provide clear **Decline** and **Continue with the selected operation** actions.
Decline must produce no inspection, copying, indexing, model request, or upload of
selected data. The user must be able to correct the selection before continuing.
The private portal implements separate unchecked terms, privacy, scope, and
eligibility controls. The selected deployment must supply accurate recipient
and operating disclosures. Its presence in source is not evidence that a real
account has completed the interaction or that counsel has approved the draft.

A prepared operation binds its kind, immutable parameters, exact source grant,
input digest, and reserved storage estimate. A separate authenticated review
binds that parameter digest. Starting consumes one review. Repeating the same
principal-scoped idempotency key returns the same operation; a new deliberate
capture needs a new review. Approval does not confer access to a newly created
generation or its download package. Each requires its own scope acceptance.

An active operation remains bound to the reviewed primary grant ID, version, and
acceptance receipt. Later acceptance does not replace that authority within the
existing plan. If it expires or is withdrawn before publication authorization,
new work requires a newly prepared and reviewed plan.

## 5. Optional and Destructive Operations

Future cloud or AI consent must identify the provider and purpose and explain
what will leave the local environment. Use an independent unchecked choice.
Training or provider reuse requires explicit treatment and must not be hidden
inside general acceptance.

Future destructive actions require a separate action-specific confirmation after
showing the exact affected source objects, reversibility, and recovery limits.
Refusing that action must not be treated as refusing an already authorized
nondestructive operation. No source-deletion permission is available in this
reference release.

## 6. Changes and Withdrawal

A material document or processing change invalidates any assumption that an old
version authorizes the new behavior. Ask for the appropriate new decision before
the affected operation starts. Stop future admission and disclosure when the
user declines or withdraws the authorization that supports it, subject to
applicable law. The journal serializes
revocation against the durable publication-authorization decision. A revocation
committed first prevents publication; a decision committed first can allow
verified private publication to finish. Later delivery is rechecked, including
the lineage of derived outputs. Previously transmitted bytes cannot be recalled.

Completed and partially completed results retain their historical plans. To
access them later, the owner must hold current explicitly accepted permission
for each ancestor's exact resource, generation, and action, in addition to the
requested result's own scope. A fresh acceptance can renew an expired or withdrawn
ancestor without changing history. Acceptance of a child collection alone cannot
override a parent that remains unauthorized. Completed-operation status withholds
output identifiers and results until the creating scope and ancestry are
currently authorized.

Download permission and package availability are separate limits. The service
checks the selected download grant, browser session, package expiry, and ancestry
before and after every streamed frame read. Expiry stops further delivery even
when another permission remains live. New consent does not extend that package's
retention period or recreate removed content.

Withdrawal does not silently delete existing outputs or restore a previous source
state. Explain those consequences and provide the relevant local controls or
Company privacy-request route.

## 7. Verification Requirements

Tests must show that missing or mismatched acceptance prevents calls to the
archive service, that all supported operations require both accepted versions, and
that a valid request records the correct operation without implying a broader
grant. The private service tests additionally cover identity separation, exact
policy digests, challenge replay, cross-origin requests, revocation ordering,
independent operation review, explicit ancestor renewal, immutable active-plan
authority, and expiry during package transmission. A production assessment must
examine document availability, understandability, accessible decline controls,
scope correction, tamper-resistant evidence where needed, and withdrawal.
Passing the prototype tests alone is not proof of production legal compliance.
