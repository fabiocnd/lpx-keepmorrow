# Trusted Human Portal

**Owner:** Lopix Neural Inc.
**Status:** Implemented private application boundary with synthetic HTTP verification
**Review date:** 2026-11-12

## Independent human authority

The browser portal owns policy acceptance, selected-content eligibility,
operation review, and uploads. It uses a session cookie independent of MCP's
bearer authentication. A model cannot create acceptance through a tool Boolean,
current version strings, a bearer token, or an operation-start call. The HTTP
boundary requires its authenticated browser session and deliberate interaction.

`create_portal(service, verifier=None)` returns a Starlette application. The
hosting entry point owns worker startup, maintenance, shutdown, and any mounted
MCP application. The portal itself does not start background workers or deploy
a service. Static assets are bundled under `integrations/chatgpt/portal_assets`.

Every authenticated control or content mutation requires the exact configured
`Origin`, a valid session cookie, and `X-CSRF-Token`. Sign-in establishes that
session through one of the credential protocols below; it cannot record consent
or authorize an operation. The CSRF value is a domain-separated digest of the
random cookie, not the cookie itself. Host validation rejects alternate authorities.
Responses use no-store caching, a no-referrer policy, MIME sniffing protection,
and a content security policy that limits executable assets to this service and
prevents framing. The portal is opened as a separate trusted page from ChatGPT.

Sessions last at most 15 minutes, and an OAuth-backed session cannot outlive the
verified access token used to create it. Cookies are HttpOnly and SameSite=Lax;
OAuth-mode cookies additionally require HTTPS. Stored session and challenge
identifiers are SHA-256 digests. Logout removes the session and its outstanding
challenges. At most 100 unexpired sessions and 32 live challenges per session
are admitted. A challenge expires within five minutes and binds an exact object,
interaction kind, and displayed-document digest.

Session and challenge expiry are sampled after acquiring the write transaction.
Waiting on database contention cannot turn an expired gesture into acceptance.
The consent handler consumes its challenge and records its receipt in the same
SQLite transaction. Neither record commits if the other operation fails.
The same transaction retains a minimal context record linking the receipt and
interaction to the displayed scope's SHA-256 digest and eligibility-declaration
version. That evidence survives session and challenge cleanup without retaining
cookies, submitted free text, or source content.

## Two explicit authentication modes

### Local operator

Operator mode is restricted to a single configured local identity and
`http://127.0.0.1:<configured-port>`. The CLI provisions a random 256-bit key in an
owner-only `operator.key` file. The portal validates the file's type, link count,
permissions, and bounded format without printing it. `POST /auth/operator`
accepts that key in a bounded JSON body over loopback, compares its digest in
constant time, and creates a fresh session. It never stores the submitted key in
the session database or uses a URL parameter for it.

This mode is a local operator workflow, not OAuth or remote ChatGPT account
authentication. It must not be exposed publicly or used as an API-key substitute
for the remote integration. No login-attempt ledger or network-edge rate limiter
is implemented by this mode; the random key and loopback restriction are its
explicit access boundary.

### External issuer

OAuth mode uses the operator's registered browser client and configured HTTPS
authorization and token endpoints. `/auth/login` creates a five-minute,
single-use state value and S256 PKCE proof. `/auth/callback` requires the matching
HttpOnly state cookie, exact state, bounded authorization code, and a live server
attempt before exchanging the code. At most 100 pending attempts are retained.
The callback URI and resource indicator come only from configuration.

The token exchange uses the same configured `/mcp` audience as the resource
server, no redirects, no ambient proxy settings, a ten-second total timeout, and
a 64 KiB uncompressed response limit. A configured confidential client obtains
its secret only from its dedicated `LPX_*` environment variable. Public clients
use PKCE without a fabricated secret. The returned access token must pass the
[external verifier](external-authentication.md), match the registered browser
client, identify an explicitly allowed principal, and remain unexpired. No raw
token is persisted. No refresh token is requested or retained.

PKCE's S256 exchange follows [RFC 7636](https://www.rfc-editor.org/rfc/rfc7636.html).
The explicit resource parameter follows
[RFC 8707](https://www.rfc-editor.org/rfc/rfc8707.html). Actual provider registration,
callback approval, token profile compatibility, and live account connection
remain deployment evidence, not consequences of passing a synthetic test.

## Human decisions and API shapes

The following APIs return plain JSON. Errors contain only `error_code` and a
fixed `message`; exception causes, credentials, request text, and source paths
are not returned. JSON inputs are capped at 64 KiB, 24 nesting levels, and a
bounded token count. Duplicate fields, unknown fields, unsupported parameters,
and coerced Boolean consent values are refused. Output JSON is bounded by the
same 512 KiB ceiling used by the MCP boundary.

| Endpoint | Responsibility |
| --- | --- |
| `GET /api/config` | Public mode and sign-in route metadata |
| `GET /api/session` | Session CSRF value, expiry, owned options, and current accepted grants |
| `GET /api/options` | Bounded owned-resource metadata pagination |
| `POST /api/consent/prepare` | Administrative grant and single-use challenge for exact resource, generation, and actions |
| `POST /api/consent/accept` | Atomically consume the displayed-scope challenge and record human acceptance |
| `POST /api/grants/revoke` | Revoke the owner's exact grant version |
| `POST /api/query` | Bounded browse, literal search, revision read, or integrity verification |
| `POST /api/operations/prepare` | Create an immutable import, recovery, association, package, or unpack plan |
| `GET /api/plans/{plan_id}` | Reauthorize and show the owned plan with a review challenge |
| `POST /api/plans/{plan_id}/review` | Record the exact human-reviewed plan digest; do not start work |
| `POST /api/operations/start` | Start an already reviewed plan under a principal-scoped idempotency key |
| `GET /api/operations` | Owned status page, with disclosure rechecked by the service |
| `POST /api/operations/{operation_id}/cancel` | Request cooperative cancellation without releasing live worker ownership |
| `POST /api/uploads` | Stream a previously consented workspace upload |
| `GET /api/downloads/{resource_id}?generation=...` | Verify and stream an exactly authorized package |
| `POST /auth/logout` | End the browser session and outstanding gestures |

Consent preparation exposes terms and privacy versions and byte digests,
purpose, recipient, exact actions, immutable generation, the fixed authorization
deadline, and the versioned content-eligibility declaration. `expires_at` is the
grant's integer Unix timestamp in seconds. The portal displays it explicitly in
UTC and includes the same value in the challenge-bound declaration.

Acceptance requires that exact displayed snapshot, including the integer
`expires_at`, and four literal `true` declarations: accepted terms, acknowledged
privacy, authorized scope, and eligible content. The handler compares the
deadline with the current grant inside the acceptance transaction and records
that same deadline on the receipt. Waiting before submission cannot extend it.
A missing, modified, or non-integer deadline is refused. A material scope or
policy change invalidates the challenge. Model-reported eligibility is not a
substitute for this interaction. The service's actual eligibility policy still
determines which material may be connected.

The grant lasts one hour from preparation. This authorization deadline is
separate from the challenge's five-minute maximum and the session's fifteen-minute
maximum; the form or sign-in can expire earlier. A new deliberate preparation
and acceptance is required for renewed authority. Previously accepted grants
retain their recorded deadlines. Forms prepared before the deadline field was
added cannot be submitted against the updated contract; reload and review a
fresh scope.

Operation review is independent of consent and start. The review challenge binds
the immutable plan's canonical digest; changing the input handle, digest,
selection, source generation, or grant invalidates that reviewed intent.
Preparation and upload have their own prior authorization. Reviewing a later
operation does not retroactively authorize earlier intake.

When an ancestor's grant expires or is withdrawn, accepting a derived collection
or package alone does not restore access. The owner must also deliberately renew
the ancestor's exact resource, generation, and action through the consent flow.
Current permission can restore disclosure of completed results while their
historical plans, receipts, and preserved bytes remain unchanged. Existing
uncompleted plans keep their original grant/version/receipt fence and require
new preparation and review rather than automatic rebinding to fresh consent.
Completed-operation status applies the creating scope and ancestry checks before
returning output identifiers and results. Renewing permission does not extend a
package's independent access lifetime.

`/policies/terms` and `/policies/privacy` return the exact cached policy bytes as
plain text. Their digests are the values bound to the acceptance record.

## Bounded upload and delivery

Upload requires `Content-Type: application/octet-stream`, a valid declared
`Content-Length` within the configured upload limit, and URI-encoded
`X-File-Name` display metadata. The filename does not select a storage path.
Workspace upload consent is checked before requesting body data. The application
allows two concurrent HTTP intake streams. Its synchronous upload store reserves
storage before writing the first byte.

The asynchronous body feeds a four-frame queue of 64 KiB frames. Backpressure
prevents an unbounded application buffer, and no intermediate spool bypasses
the upload store's reservation. A producer and reader frame are additional
bounded memory; the HTTP server owns its incoming network buffers. The stream
must match its declared size exactly. Session and exact-grant authority are
checked for each frame returned to the preservation layer.

A disconnect signals failure to the receiver and waits for its owned staging
and reservation cleanup. Cancelling a thread future alone does not terminate
its thread, so the bridge retains the intake slot until the receiver actually
returns. No timeout or disconnected client silently releases a live reservation.

Download first checks the exact package grant, its originating operation's
authority, and the independently verified package bytes. It streams in 64 KiB
frames and rechecks the session, download grant, package availability/expiry,
and authorized ancestry before and after each disk read. The selected download
grant remains fixed for that stream. Revocation, authorization loss, or package
expiry ends further delivery; another newly accepted grant does not silently
replace it. A prematurely ended response does not satisfy its declared
Content-Length; bytes already sent cannot be recalled. The stream context closes
on normal completion, authorization loss,
response-start failure, cancellation, or client disconnect.

No public bearer download URL is issued. The portal does not claim native
ChatGPT file delivery or restoration, and downloading a verified local package
does not prove a remote copy's integrity without a separate verification step.

## Lifecycle and retained records

The combined application starts the exclusive worker and recovery maintenance
before admitting requests. A startup failure is reported with a fixed message
and no original exception chain, and shielded shutdown still attempts to stop
the worker. A live worker retains ownership until it actually stops; cancellation
does not release its process lock for a competing attempt. Periodic maintenance
reports fixed error categories without request text, paths, or content.

Session and challenge cleanup does not remove the retained acceptance context,
grant evidence, or immutable operation history. The access store bounds live
grants per principal, and the application uses a 64 MiB metadata admission
threshold to stop continued pilot growth. Neither is an automatic long-term
purge policy or a guarantee that the database never exceeds that byte count.
The actual operator must qualify metadata retention, backups, incident handling,
and disposal before production. The [Privacy Notice](../../legal/privacy-notice.md)
distinguishes persistent collections from temporary uploads and package wrappers.

## Observed verification and remaining limits

Synthetic tests exercise cookie-only authentication, Host/Origin/CSRF refusal,
literal consent choices, scope and digest fencing, replay, pre-I/O access denial,
cross-principal isolation, byte-exact uploads, independent review and start,
idempotency, a real worker package and hash-verified HTTP download, mid-stream
revocation and package expiry, and explicit ASGI upload/download disconnect
cleanup. Application tests cover explicit ancestor renewal and refusal to rebind
active plans. A lifecycle regression verifies safe startup failure and worker
lock release. OAuth tests use a synthetic token endpoint and verifier and validate
state, PKCE, client,
resource, cookie, and callback replay behavior.

Those tests do not establish a live identity-provider login, real ChatGPT
connection, public availability, legal enforceability, hostile-host isolation,
network-edge traffic control, or a production storage and retention envelope.
The configured operator retains responsibility for TLS termination, protected
storage, backups, current policies, provider compatibility, and release review.
