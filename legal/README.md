# Legal Documents and Release Status

**DRAFT FOR OWNER AND QUALIFIED ONTARIO COUNSEL REVIEW**  
**Document set version:** `2026-11-12-draft.1`  
**Prepared:** 2026-11-12  
**Production effective date:** Not assigned

These documents are an internal drafting package for LPX Keepmorrow. They are
not an approved or effective production contract, a finding of legal compliance,
or authorization to launch a public service. The prototype's acceptance flags
exercise a technical control against these drafts; they do not establish that
counsel has approved the documents or that a particular contract is enforceable.

## Documents

| Document | Purpose |
| --- | --- |
| [Terms of Use](terms-of-use.md) | Proposed user responsibilities, product limitations, ownership, and lawful protections for Lopix Neural Inc. and Fabio de Sousa Lopes. |
| [Privacy Notice](privacy-notice.md) | Current local data handling, user-controlled retention, privacy choices, and requirements before introducing remote processing. |
| [Consent and Operation Authorization](consent-and-operation-authorization.md) | Separate agreement, privacy, and operation choices; the implemented CLI gate and future interface requirements. |
| [Legal Basis](../docs/research/legal-basis.md) | Official sources, reviewed provisions, drafting rationale, and questions for counsel. |

The company is the proposed contracting party. Fabio de Sousa Lopes is expressly
identified as a protected developer only to the extent a lawful exclusion or
limitation can benefit him. No clause promises either party immunity from every
claim or excuses a duty that cannot be waived.

## Current Implementation Boundary

The reference application operates on explicitly selected local directories. It
creates a portable archive, checks its recorded inventory and file hashes, and
restores supported files into a new directory. It has no application network
requests, model inference, automatic telemetry, cloud connector, or source
deletion operation. Storage synchronization performed by the user's operating
system or another application is outside that description.

Each `create`, `verify`, or `restore` CLI invocation requires both exact options:

```text
--accept-terms 2026-11-12-draft.1
--accept-privacy 2026-11-12-draft.1
```

Missing or mismatched acceptance must stop the command before selected user data
is inspected. The operation and path arguments define that invocation's requested
scope. The local JSON acceptance metadata records document versions, a UTC time,
and the operation. It is not an authenticated identity record, a complete scope
ledger, a digital signature, or evidence of a completed archive operation.

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
