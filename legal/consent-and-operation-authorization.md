# Consent and Operation Authorization

**DRAFT FOR OWNER AND QUALIFIED ONTARIO COUNSEL REVIEW**  
**Document version:** `2026-11-12-draft.1`  
**Prepared:** 2026-11-12  
**Production approval:** Not granted by this document

This document defines the internal consent-control behavior and proposed
production interaction. It does not certify the enforceability of the draft
[Terms of Use](terms-of-use.md) or [Privacy Notice](privacy-notice.md).

## 1. Separate the Decisions

| Decision | Meaning | Current reference status |
| --- | --- | --- |
| Accept the stated Terms version | Deliberate agreement to the presented document, subject to mandatory law | Required CLI version flag; draft documents only. |
| Acknowledge the stated Privacy Notice and authorize necessary local processing | Understanding of the described data handling and authorization for the requested local action | Required CLI version flag; no optional processing is bundled. |
| Request an operation | Select `create`, `verify`, or `restore` and its source and destination arguments | Explicit CLI command and arguments. |
| Authorize cloud transfer or model use | Approve a specified recipient, purpose, data selection, and consequences | Unavailable; requires separate future implementation and consent. |
| Authorize a destructive source action | Approve named objects and a specific deletion, overwrite, move, or mutation | Unavailable; no current source-deletion operation. |

Agreement to terms is not itself authorization for every possible use of data.
Document acceptance and operation authorization must both exist before accessing
the selected material. Do not infer either from silence, a preselected checkbox,
the mere presence of files, a previous operation, or continuation after an error.

## 2. Current CLI Gate

Each operation requires these exact values:

```text
--accept-terms 2026-11-12-draft.1
--accept-privacy 2026-11-12-draft.1
```

The caller must be able to read the two versioned documents before supplying the
flags. Missing, outdated, or mismatched acceptance prevents the archive service
from inspecting or processing the selected data. Help and legal-document access
must remain available without accepting an operation.

For an internal synthetic-data evaluation, an explicit command takes this form:

```bash
python -m keepmorrow create ./synthetic-source ./new-archive \
  --accept-terms 2026-11-12-draft.1 \
  --accept-privacy 2026-11-12-draft.1
```

The source, destination, and operation arguments specify the current invocation.
The flags must not be silently inserted by an end-user wrapper or derived from
an unrelated approval. A scheduled job would need a separately reviewed
authorization describing its recurring scope, duration, and revocation behavior;
these per-invocation flags do not supply that production workflow.

The CLI is the implemented end-user boundary. Internal Python functions are
engineering interfaces. Before exposing another entry point, its implementer
must enforce equivalent acceptance and scope checks; the present CLI gate is not
a claim that arbitrary direct calls to internal functions authenticate a user.

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

For a future public interface, determine the least amount of evidence needed to
link the presented document versions, explicit action, approved purpose, and
scope. A suitable design may include immutable document digests, an operation
identifier, an appropriate user/session identifier, a scope reference, and the
resulting consent state. That design is not implemented here. It requires a
retention schedule, access controls, and protection against alteration; it must
not copy private content into a consent log unnecessarily.

## 4. Proposed End-User Presentation

Present the product's actual operator and both documents near the decision. Show
the requested action and selected source and destination before the user confirms
processing. Use accessible, separately selectable controls with no preselection.

Proposed text for the agreement control:

> I have had the opportunity to read and agree to the LPX Keepmorrow Terms of Use
> shown here, version [displayed version].

Proposed text for the privacy and necessary-operation control:

> I have reviewed the Privacy Notice, version [displayed version], and authorize
> the necessary local processing of the selected material for the operation
> shown here.

Proposed operation confirmation:

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
This proposed graphical interaction is a requirement for later implementation,
not a screen already supplied by the reference CLI.

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
the affected operation starts. Stop future processing when the user declines or
withdraws the authorization that supports it, subject to applicable law.

Withdrawal does not silently delete existing outputs or restore a previous source
state. Explain those consequences and provide the relevant local controls or
Company privacy-request route.

## 7. Verification Requirements

Tests must show that missing or mismatched acceptance prevents calls to the
archive service, that all three operations require both accepted versions, and
that a valid request records the correct operation without implying a broader
grant. A production assessment must additionally examine document availability,
understandability, accessible decline controls, scope correction, tamper-resistant
evidence where needed, and withdrawal. Passing the prototype tests alone is not
proof of production legal compliance.
