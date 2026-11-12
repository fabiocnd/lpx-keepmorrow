# Private Deployment Examples

These files describe a reviewable deployment candidate. They do not provision a
host, create an identity provider, register an OAuth client, expose a port, or
establish a ChatGPT connection. All values under `example.com` are placeholders.

## Local operator evaluation

Install the pinned optional service dependencies and use `keepmorrow-service
init /absolute/path/to/new-service`. The directory must be new. Initialization
copies the current policy drafts, creates an owner-only operator key, and writes
an empty configuration. Read the key only on the operator's device and enter it
only in the loopback portal. The key is never a ChatGPT authentication method.

Run `keepmorrow-service check --configuration /absolute/path/to/new-service/service.json`
before `keepmorrow-service serve --configuration /absolute/path/to/new-service/service.json`.
The local portal is available at `http://127.0.0.1:8765` on that same machine.
It exposes no MCP endpoint in operator mode.

## Authenticated service candidate

Copy [oauth-service.example.json](examples/oauth-service.example.json) into
operator-controlled configuration outside the repository. Supply the actual
issuer, audience origin, JWKS endpoint, registered browser client, and exact
allowlisted issuer/subject identity. The browser callback is
`https://YOUR-ORIGIN/auth/callback`. The MCP resource is
`https://YOUR-ORIGIN/mcp`; protected resource metadata is available at
`https://YOUR-ORIGIN/.well-known/oauth-protected-resource/mcp`.

The browser client uses authorization code with PKCE S256 and the
`keepmorrow:access` scope. A confidential client may name a dedicated
`LPX_...` environment variable for its client secret. Secret values belong in
the service's credential environment, never JSON, Git, URLs, UI state, or logs.
The selected provider must issue supported user access tokens; machine tokens
and arbitrary ID tokens are refused. Review the exact
[token profile](../docs/architecture/external-authentication.md).

Keep the application on loopback. The
[systemd unit](systemd/keepmorrow.service) and
[reverse-proxy example](nginx/keepmorrow.conf.example) require an operator-created
unprivileged account, installed environment, private directories, a real TLS
certificate, and the selected proxy host. Do not copy placeholders into a live
service. The proxy must preserve the exact configured Host, limit request bodies,
and disable content-bearing access logs. Forwarded headers are not trusted by
the application. This candidate has not been provisioned in the current session.

The application enforces a single process-exclusive worker. Run one service
process against an owner-controlled local filesystem; SQLite files, lock files,
output trees, and workspaces must not be replaced while it runs. Network filesystems,
multiple replicas, container orchestration, and cross-host workers have not been
qualified. Archive staging and publication require one filesystem.

## ChatGPT connection gate

Use the target account's available custom-MCP installation path only after
identity, recipient disclosures, and synthetic interaction are confirmed. A
Secure MCP Tunnel is a private-pilot candidate; availability, organization
permissions, and the actual tunnel client remain to be verified. The OAuth
authorization server is not automatically reachable through a tunnel.

No model tool supplies acceptance or review. In ChatGPT, prepare an operation,
open the trusted portal to review it, then start that exact reviewed plan. Use
the companion for explicit reads and status. Raw local uploads and generated
downloads use the authenticated portal. Native ChatGPT file-picker acquisition
has not been integrated; the application never downloads arbitrary file URLs.

Before real content is connected, identify the operator, hosting region,
subprocessors, access process, content eligibility, backup policy, long-term
metadata retention, and incident owner. Obtain the reviewed legal and user
decisions for that actual scope. See the
[operating runbook](../docs/operations/private-service-runbook.md) and
[execution evidence](../docs/engineering/private-pilot-validation.md).
