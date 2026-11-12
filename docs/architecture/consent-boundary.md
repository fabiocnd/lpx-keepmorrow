# Consent and Operation Boundary

**Status:** Local reference implementation; internal legal drafts
**Terms version:** `2026-11-12-draft.2`
**Privacy version:** `2026-11-12-draft.2`
**Owner:** Lopix Neural Inc.
**Contact:** fabio@lopixneural.com

The ordinary CLI and optional MCP adapter must obtain explicit acceptance of
both current policy versions before reading selected source or collection
content. Missing, stale,
malformed, or unsupported declarations fail closed. Argument parsing and loading
the application itself do not inspect selected user content.

Review [Terms of Use](../../legal/terms-of-use.md),
[Privacy Notice](../../legal/privacy-notice.md), and
[Consent and Operation Authorization](../../legal/consent-and-operation-authorization.md)
before declaring acceptance. These drafts apply to internal evaluation; accepting
them does not authorize public release.

## Boundary contract

`keepmorrow.consent.require_acceptance(terms_version, privacy_version, operation)`
accepts exact current version strings and one of `create`, `verify`, `restore`,
`import`, `catalog`, `search`, `read`, `associate`, or `recover`.
It performs no file or network access. Any other value raises `ConsentError`.

Acceptance is limited to the selected local operation and its explicit paths.
It does not authorize deletion, cloud transfer, AI processing, training, account
enumeration, source redistribution, or public publication. Selecting an
operation does not override filesystem validation, archive-integrity checks, or
the prohibition on overwriting an existing destination.

The CLI requires both `--accept-terms VERSION` and `--accept-privacy VERSION` for
each invocation of a processing command. Use the flags after the operation name.
There is no remembered acceptance and no implicit `latest` version. A changed
policy version therefore requires a new exact declaration.

```bash
PYTHONPATH=src python -m keepmorrow create examples/synthetic-input /tmp/keepmorrow-example \
  --accept-terms 2026-11-12-draft.2 \
  --accept-privacy 2026-11-12-draft.2
```

The internal archive, importer, and catalog functions remain implementation primitives.
Direct Python calls are not an authenticated user-facing API and do not enforce
acceptance themselves. Embedding applications must put an equivalent boundary
before every user-content operation and must not expose these primitives as an
ungated service.

## MCP development boundary

Every MCP tool requires `terms_version` and `privacy_version`.
The server checks them before resolving the selected
collection grant or inspecting registered content. Its registry uses explicit
opaque IDs; request arguments cannot select arbitrary filesystem paths. Registry
configuration loading does not inspect the contents of its registered paths.

The adapter exposes only collection listing, browsing, search, revision reading,
and verification. Results are returned to the calling client. Loopback transport
is a development restriction, not remote authentication or authenticated proof
of the user's agreement. The adapter does not implement a consent presentation
UI or a durable acceptance ledger. A deployed ChatGPT interface must present the
policies, record a deliberate user decision, enforce collection authorization,
and describe that client's data handling before content access. See
[ChatGPT integration](chatgpt-integration.md).

## Receipt and persistence

After validation, the boundary returns an immutable receipt containing the
accepted terms version, privacy version, UTC timestamp, and operation name. It
contains no user identity, credential, source path, conversation text, or file
content. The receipt records a local declaration; it does not prove who made
that declaration or establish cryptographically verifiable assent.

CLI JSON status includes the receipt as `acceptance`: on stdout for normal
results, or stderr when an accepted operation fails. The caller controls any
explicit capture of that output. The application does not send the receipt to a
service or persist it in a consent database. Refused operations produce no
receipt. An accepted operation can still fail validation or execution; its
receipt must not be interpreted as a completion or integrity result.

This persistence limit is deliberate for the current local reference. A future
authenticated product needs a separately designed record of the document
versions presented, the authenticated actor or other permitted attribution,
acceptance event, operation scope, retention, revocation behavior, and integrity
of the record. Implementing that system requires an explicit data-handling
design and appropriate legal review; the CLI receipt is not its substitute.

## Verification scope

Tests establish refusal for missing or stale acceptance and unknown operations,
exact version matching, receipt scope, and CLI and MCP rejection before services
or selected content are inspected. They also show that
explicit current acceptance allows the ordinary archive validation path to run.
These tests establish the application boundary described here, not the legal
enforceability of the draft terms.
