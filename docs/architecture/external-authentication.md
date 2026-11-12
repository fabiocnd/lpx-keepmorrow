# External Access-Token Verification

**Owner:** Lopix Neural Inc.
**Status:** Implemented optional resource-server verifier; no production identity provider selected
**Review date:** 2026-11-12

## Purpose and integration

`ConfiguredTokenVerifier` implements the MCP SDK's asynchronous `TokenVerifier`
contract. It returns an `AccessToken` only after verifying an external issuer's
access token. It does not register clients, implement an authorization server,
mint tokens, establish account linking, or replace the trusted human acceptance
interaction. No issuer or hosted service has been provisioned by this module.

The server constructs `AuthenticationConfig` with the actual issuer, its
preapproved HTTPS JWKS URL, the exact resource audience, and required scopes.
For the current application, the resource is its configured `/mcp` URL and the
required scope is `keepmorrow:access`. Values are operator configuration, never
model arguments or URLs extracted from a token.

After verification, derive `Principal(access_token.claims["iss"],
access_token.subject)` from the SDK's verified request context. Apply the
application's allowed-principal filter and the persistent access and acceptance
checks before reading content. A valid token does not grant access to a resource.

The returned SDK object contains the request's raw token because the SDK contract
requires it. Never log, serialize to user-visible output, or persist that object.
The additional claims field contains only the verified issuer; email addresses
and unrelated provider claims are not copied into application metadata.

## Application composition

The private application mounts the complete SDK HTTP application, including its
authentication and token-context middleware. Copying its routes without that
middleware is not an equivalent integration. MCP tools read only the SDK's
verified request context and then enforce the configured allowlist of at most
ten exact issuer/subject identities. No request argument can select an identity.

The browser portal has its own short-lived authenticated cookie. That cookie
cannot replace a bearer token at the MCP endpoint. Conversely, a verified bearer
token does not satisfy the portal's session, Origin, CSRF, and deliberate-human
interaction checks. Local operator mode exposes no MCP endpoint and does not
imitate an external issuer. See [trusted portal](trusted-portal.md) for the
browser login and acceptance contract.

Configuration, policy, and worker-startup failures prevent application startup.
Worker-startup errors reaching the ASGI server use a fixed diagnostic with the
original exception chain suppressed; private state paths and underlying
filesystem messages are not included in that diagnostic. Worker ownership
cleanup still runs. This behavior does not configure a host, issue a certificate,
or verify a provider registration.

## Supported token profile

The implementation deliberately supports one bounded profile:

| Field or behavior | Enforcement |
| --- | --- |
| Signature | RS256 with a configured provider's public RSA key |
| Public key | 2048–4096 bits, exponent 65537; no private key material |
| Token type | `at+jwt` or `application/at+jwt` by default |
| Issuer | Exact configured HTTPS issuer |
| Audience | Configured HTTPS resource present in a string or bounded audience list |
| User identity | Nonempty subject; explicit service-client grants and subject/client equality refused |
| Client identity | `client_id`, or `azp` when absent; both must agree when supplied |
| Time | Required integer `iat` and `exp`; optional integer `nbf`; bounded lifetime |
| Scope | Standard space-separated `scope`, including every configured required scope |
| JSON | Duplicate fields and nonstandard numeric values refused |
| Headers | Unsupported algorithms, critical extensions, embedded keys, and key URLs refused |

Token type `JWT` requires an explicit operator-reviewed configuration change for
an issuer whose access-token profile uses that type. Do not enable it merely to
make an identity token pass. Opaque access tokens, encrypted JWTs, other signature
algorithms, and provider-specific scope formats are not supported by this
verifier. A provider that needs them requires a separate reviewed adapter.

The default maximum token lifetime is one hour, with zero clock-skew allowance.
Operators may configure a lifetime up to one day and skew up to 60 seconds when
the chosen provider requires it. Time is checked before and after key retrieval
so a token that expires while awaiting the provider is refused. The SDK or other
boundaries may enforce the returned expiry independently and more strictly.

Rejecting recognizable service-client grants does not cryptographically prove a
human is present. The chosen issuer must provide unambiguous user-subject
semantics; the application must allow only its configured pilot identities and
verify the human's separate interactive decision.

## Bounded key retrieval and cache behavior

The default fetcher uses only the configured HTTPS JWKS URL, refuses redirects
and compressed responses, sends no credentials or cookies, and ignores ambient
proxy settings. It enforces a total five-second timeout and a 256 KiB uncompressed
response bound. No `jku`, `x5u`, issuer claim, or embedded JWK can select another
network destination. A deployment needing a specific outbound proxy must
provide and review an explicit transport rather than inherit unrelated process
environment settings.

At most 32 keys are parsed. A cache lasts five minutes by default. One refresh
runs at a time, and a global ten-second cooldown bounds refresh requests caused
by unknown key IDs or forged signatures. Rotation to a new key ID is observed
after that cooldown. A changed key using the same ID can receive one refresh and
signature retry. A legitimately new key can therefore be temporarily refused
while the cooldown remains active; this is a deliberate bounded failure mode.

An expired cache is never used after a failed refresh. Still-current cached keys
can remain usable until their TTL; external key withdrawal is therefore not an
instantaneous revocation channel. Application grant revocation remains an online
database check on admission and delivery. A new deployment must qualify provider
key-rotation and emergency-revocation procedures against this cache behavior.

`fetch_jwks: Callable[[], Awaitable[bytes]]` is an injectable trusted-server seam
for deterministic tests or an explicitly reviewed transport. Returned data still
passes byte, JSON, key count, key type, and cryptographic parameter limits.
Request cancellation propagates. Every ordinary verification failure returns
`None`, without a token, claim body, network URL, or exception message in logs.

## Dependencies and evidence

The implementation was exercised locally with MCP 1.29.0, PyJWT 2.13.0,
cryptography 50.0.0, and HTTPX 0.28.1. These are optional ChatGPT integration
dependencies; the archive core remains standard-library-only. The installed MCP
`TokenVerifier` and `AccessToken` definitions and PyJWT decode interface were
inspected directly before implementation.

The fixed algorithm and audience checks follow the JWT implementation guidance
in [RFC 8725, Sections 3.1 and 3.8–3.12](https://www.rfc-editor.org/rfc/rfc8725.html).
The default access-token types and distinction from identity tokens follow
[RFC 9068, Sections 2 and 4](https://www.rfc-editor.org/rfc/rfc9068.html). The
implementation uses a selected provider profile and does not claim complete
conformance with every RFC 9068 claim requirement; for example, it does not
require `jti` and explicitly permits an `azp` client-identity mapping.

[PyJWT's API documentation](https://pyjwt.readthedocs.io/en/stable/api.html)
explains the difference between requiring claim presence and validating its
value, and warns against deriving allowed algorithms from token input. This
module fixes the algorithm and performs explicit bounded shape and time checks
in addition to library signature, issuer, and audience verification. Version-
specific behavior was checked against the installed package rather than assumed
from an evolving documentation page.

Synthetic tests cover valid and forged signatures; missing, stale, or malformed
claims; issuer, audience, and scope isolation; service-client rejection; key
rotation; cache failure; duplicate metadata; private or weak key rejection;
redirect, compression, and byte limits; expiry during retrieval; and cancellation.
Optional tests skip when the integration dependencies are absent. No real
identity-provider login, callback configuration, account capability, or hosted
deployment has been demonstrated by these tests.
