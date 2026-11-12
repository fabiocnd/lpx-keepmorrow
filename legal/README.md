# Legal Documents and Release Status

**DRAFT FOR OWNER AND QUALIFIED ONTARIO COUNSEL REVIEW**
**Terms version:** `2026-11-12-draft.4` · **Privacy version:** `2026-11-12-draft.3`
**Prepared:** 2026-11-12
**Production effective date:** Not assigned

These documents are an internal drafting package for LPX Keepmorrow. They are
not an approved or effective production contract, a finding of legal compliance,
or authorization to launch a public service. The local acceptance flags and
private portal exercise technical controls against these drafts; they do not
establish counsel approval or the enforceability of a particular contract.

Project-owned source in this revision uses Apache License 2.0. These processing
drafts do not restrict or condition the rights that license grants. Source
licensing does not establish privacy compliance, approve hosting, or grant access
to user accounts. Terms draft.4 corrects the source-license disclosure; privacy
remains draft.3. Changed policy bytes and versions require fresh acceptance.

## Documents

| Document | Purpose |
| --- | --- |
| [Terms of Use](terms-of-use.md) | Proposed user responsibilities, product limitations, ownership, and lawful protections for Lopix Neural Inc. and Fabio de Sousa Lopes. |
| [Privacy Notice](privacy-notice.md) | Local and private-service data handling, bounded temporary transfers, retained control records, privacy choices, and requirements before live connected processing. |
| [Consent and Operation Authorization](consent-and-operation-authorization.md) | Separate agreement, privacy, eligibility, scope, and operation-review decisions; implemented boundaries and remaining production review. |
| [Legal Basis](../docs/research/legal-basis.md) | Date-scoped official-source review, drafting rationale, and unresolved questions for counsel. |

The company is the proposed contracting party. Fabio de Sousa Lopes is expressly
identified as a protected developer only to the extent a lawful exclusion or
limitation can benefit him. No clause promises either party immunity from every
claim or excuses a duty that cannot be waived.

## Current Implementation Boundary

The local core operates on explicitly selected supported files, directories,
and export containers. It preserves supplied bytes, derives catalogs, verifies
inventory and hashes, and recovers selected supported material into a separate
destination. The core has no outbound application network client. No current
delivery surface provides model inference, training, automatic telemetry,
whole-account capture, source deletion, or native ChatGPT restoration.

The separate private service implements an authenticated browser portal,
per-principal resource grants, deliberate policy and eligibility acceptance,
reviewed background operations, temporary uploads, and verified package
downloads. Local operator mode uses loopback and has no MCP endpoint. Configured
OAuth mode validates an external issuer's access tokens and exposes authorized
MCP requests; it contacts only explicitly configured authentication endpoints.
Neither the presence of that code nor synthetic tests establish a live provider,
ChatGPT account connection, selected hosting environment, or production approval.
The legacy unauthenticated loopback MCP adapter remains synthetic-only.

Every CLI operation that inspects selected content requires both exact options,
including import, catalog queries, association review, and selected recovery:

```text
--accept-terms 2026-11-12-draft.4
--accept-privacy 2026-11-12-draft.3
```

Missing or mismatched acceptance must stop the command before selected user data
is inspected. The operation and path arguments define that invocation's requested
scope. The local JSON acceptance metadata records document versions, a UTC time,
and the operation. It is not an authenticated identity record, a complete scope
ledger, a digital signature, or evidence of a completed archive operation.

The portal separately records exact policy versions and byte digests, scoped
grants, human interaction evidence, expiry, and revocation. Active plans remain
bound to the exact reviewed grant and acceptance. Completed-result disclosure
may use a fresh explicit acceptance of each ancestor's exact scope; permission
on a child alone cannot override an unauthorized parent. Withdrawal does not
erase immutable history or recall previously delivered bytes. Package expiry
stops further transmission even when a download grant remains live.

These controls do not establish lawful authority over another person's data or
replace retention duties. Temporary uploads and packages have bounded service
lifetimes; collections and historical control records do not have an automatic
long-term purge policy. See the Privacy Notice for the actual distinction.

## Required Before Production Release

The owner and qualified Ontario counsel must review the final delivery model,
intended users and jurisdictions, applicable laws, contract formation, developer
beneficiary wording, consumer remedies, privacy responsibilities, and actual
insurance arrangements. Review must include the reasonableness of every proposed
exclusion; no numeric liability cap is supplied by this draft.

The release must also provide the actual retention schedule for company-controlled
records, an accountable privacy contact, a request and incident-response process,
and accessible copies of the final documents. A public interface needs a tested
consent experience and appropriate evidence of the version, action, and authorized
scope. Release documentation must distinguish what is implemented from a future
control. Use synthetic data for the current internal evaluation.

Assign a production version and effective date only after those reviews and the
corresponding implementation changes. Keep prior versions available. Material
changes to processing purposes, recipients, or operation scope require a new
decision before the changed processing starts.

**Owner and project contact:** Lopix Neural Inc., attention Fabio de Sousa Lopes,
[fabio@lopixneural.com](mailto:fabio@lopixneural.com).
