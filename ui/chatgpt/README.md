# Keepmorrow MCP Apps Interface

**Publisher:** Lopix Neural Inc.
**Engineering lead:** Fabio de Sousa Lopes
**Contact:** fabio@lopixneural.com
**Status:** Implemented interface and local protocol/DOM tests; actual browser and ChatGPT host validation pending

This optional TypeScript interface accompanies the authenticated Keepmorrow
service. It uses the official `@modelcontextprotocol/ext-apps` `App` class for
host initialization, server tools, theme updates, and opening the trusted portal.
It contains no custom message transport, browser credential storage, arbitrary
file paths, or direct outbound content requests.

## User workflow

The initial connection reads access metadata only. A person explicitly loads
authorized collection references, selects an immutable generation, and chooses
Browse, Search, Read revision, or Verify. Every content request includes the
selected `collection_id` and `generation`.

Conversation cards retain historical revisions and distinguish unknown project
association from confirmed standalone status. The revision view preserves node,
parent, and child identifiers and identifies branches and truncated text. Source
titles, excerpts, messages, and identifiers enter the document through text
nodes; imported HTML, URLs, SVG, scripts, and event handlers are never activated.

Operations are inspected and cancelled through a separate request group so a
pending content read does not disable status or cancellation. Completed output
and account completeness are not inferred from interface state. The server
remains authoritative for consent, ownership, grants, operation state, and
delivery.

The secure portal owns human policy acceptance, upload, operation review, and
download. Opening it uses the host's `openLink` API. The interface accepts an
HTTPS portal URL supplied by authenticated access metadata, with HTTP allowed
only for localhost/127.0.0.1 development. Embedded credentials, query parameters,
and fragments are rejected. Imported content cannot select a portal destination.

File input and delivery use the authenticated portal's native browser file picker
and attachment response. Selecting a file does not upload it; a separate action
starts the bounded transfer. The reviewed opaque receipt identifies its exact
byte count and SHA-256. This is the implemented alternative to native ChatGPT
file-transfer features, whose availability in the intended account has not been
verified. The component does not obtain account history, previously uploaded
ChatGPT attachments, or arbitrary download URLs.

The portal separately displays current policy bytes and scope, requires four
unchecked choices, then records acceptance only on deliberate submission. A
prepared write also requires its own exact-parameter review. The UI cannot grant
authority by returning a model-supplied acceptance flag. A lost start response can
be retried with the same plan idempotency key; it does not imply that execution
never began. Interface state never overrides a changed server grant.

Read and search pages are bounded views. Truncated text and branches remain
explicit, and paging does not alter the preserved collection. A selected recovery
contains normalized selected records and byte-preserved bound artifacts; its
whole-source JSON and original ZIP can be omitted to keep unrelated conversations
out of that derivative. Binary files are copied intact and can contain additional
information. The complete originals remain in the parent collection. A recovery
package is a portable local archive, not a native recreation of ChatGPT chats,
Projects, or settings. See the
[transfer contract](../../docs/architecture/transfer-contract.md).

## Build and package

Use Node.js 24 or later. Direct dependencies and the complete resolved dependency
tree are pinned in `package.json` and `package-lock.json`.

```sh
cd ui/chatgpt
npm ci --ignore-scripts --no-audit --no-fund
npm run build
```

The build runs strict TypeScript validation and produces one self-contained HTML
resource at `dist/keepmorrow.html`. It also updates the identical wheel resource
at `src/keepmorrow/integrations/chatgpt/assets/keepmorrow.html` and the matching
third-party notice file. The release build must include those generated assets;
Python users do not need Node.js to serve a prebuilt resource.

The generated HTML currently contains approximately 690 KB of bundled source
and styles. No CDN, runtime module download, external font, or image request is
needed. The production resource does not include the synthetic host, fixtures,
or browser test controls.

An open-source transition is planned. The owner has not yet selected the exact
release license or authorized the visibility change; the current repository
license remains proprietary, and the UI package remains `private: true` with
`license: "UNLICENSED"`. This planned transition does not grant redistribution
rights to the project before that decision. Upstream packages retain their
respective licenses. `THIRD-PARTY-NOTICES.txt` is generated from packages that contribute
bytes to the production bundle and preserves their installed license texts,
including the MCP TypeScript packages' recorded licensing-transition notice.
Development tools are identified in the lockfile and are not included in the
production HTML.

The November 12, 2026 bundle audit found five contributing packages. Their
installed versions matched the lockfile, and the notice file contained the
complete installed license text for each:

| Bundled package | Version | Installed metadata and license evidence |
| --- | --- | --- |
| `@modelcontextprotocol/client` | 2.4.0 | Metadata declares Apache-2.0; the supplied license also retains the MIT transition notice |
| `@modelcontextprotocol/core` | 2.4.0 | Metadata declares Apache-2.0; the supplied license also retains the MIT transition notice |
| `@modelcontextprotocol/ext-apps` | 2.0.4 | Metadata declares MIT; the supplied license contains the MCP Apache/MIT transition text |
| `pkce-challenge` | 5.0.1 | MIT license text retained |
| `zod` | 4.6.7 | MIT license text retained |

None of these installed packages supplied a separate `NOTICE` or `COPYING` file.
The generated and wheel notice files were byte-identical. Preserve the full MCP
license text when evaluating the open-source release; the `ext-apps` metadata
label alone does not describe its supplied transition terms. This local artifact
audit establishes notice coverage, not a legal opinion on the pending project
license or every distribution arrangement. Rebuild and repeat the audit when the
lockfile changes.

## Local verification

```sh
npm test
npm run test:browser
```

`npm test` runs 28 checks: five bounded-response contracts, eight companion DOM
interactions, fourteen portal DOM interactions, and one protocol exchange with
the real SDK. The protocol test exercises initialization, tool calls, and link
opening between official `App` and `AppBridge` over the SDK's in-memory transport.
The DOM tests use synthetic records and exercise explicit content selection,
immutable generation binding, literal
search, inert hostile markup, graph and revision pagination, active cancellation,
stale-result suppression, revoked access, empty grants, and coverage reporting.

The same command also tests the production human-portal assets. Those checks
require every unchecked consent control, verify exact scope/policy snapshots and
CSRF headers, prevent automatic upload or execution, bind each preparation kind
to its strict server parameters, reject stale generation results, and exercise
lost review/start responses with a stable idempotency key. Declining an in-flight
review prevents its later start; an uncertain start is reported without claiming
that execution did not occur. These tests exercise DOM behavior without accepting
any real user's policies or submitting private files.

`npm run test:browser` is a separate Playwright gate with eight cases. It loads
the actual production resource inside a synthetic host implemented with official
`AppBridge` and `PostMessageTransport`. The suite includes a 320 px viewport,
long titles, keyboard interaction, and screenshots. It chooses an explicitly
configured `KEEPMORROW_CHROMIUM`, a local `/usr/bin/chromium`, or Playwright's
installed browser. On other machines, install the supported browser using
`npx playwright install chromium` before running the gate.

Observed on 2026-11-12 with Node.js 24.22.1:

| Check | Observed result |
| --- | --- |
| Strict TypeScript and bundle build | Passed |
| 28 contract, DOM, portal, and SDK protocol checks | Passed |
| Eight Playwright cases | Blocked before page launch: Chromium profile socket creation was denied by the executor |
| Command retry outside the sandbox | Rejected by the environment's approval policy; sandbox escalation was unavailable |
| Managed browser preview | The browser could not reach the executor's local preview; the resulting error page was then blocked by browser URL policy |
| Actual authenticated ChatGPT host | Not tested in this implementation environment |

The blocked browser suite is not represented as a passing or skipped result.
The DOM tests establish behavior without establishing layout quality, real
browser transport, host compatibility, focus appearance, or measured rendering
performance. Release review must complete those browser cases and the actual
authenticated ChatGPT upload/download and interface checks.

## Contract and integration notes

The UI expects response version 2:

```json
{
  "response_version": 2,
  "status": "ok",
  "data": {}
}
```

Errors use a bounded `error_code`; arbitrary exception messages are not rendered.
Collection pagination uses `after_grant_id` and `next_grant_id`. Operation
pagination uses `before_operation_id` and `next_before_operation_id`. Collection
content pages use bounded offsets. The UI holds presentation state in memory
and does not persist conversation content in browser storage.

The human portal uses cookie-authenticated HTTP endpoints and raw JSON response
objects, separately from the versioned tool envelope above. Its CSRF value stays
in the portal context. Only an opaque per-plan idempotency key is retained in
session storage, with an in-memory fallback; policy acceptance is not inferred
from that key. The component receives no bearer token or browser session cookie.
The portal checks download session, grant, artifact expiry, and authorization
lineage before and after each 64 KiB disk read. A revoked or expired stream stops
without a claim that already transmitted bytes were recalled. The
[trusted portal contract](../../docs/architecture/trusted-portal.md) defines those
server-side boundaries.

The server registers the HTML with MIME type `text/html;profile=mcp-app` and
associates it with the `render_keepmorrow` tool. Tool definitions remain useful
when the interface cannot load. Integration metadata, access control, OAuth,
host checks, and the trusted portal belong to the Python service.

## Primary implementation references

Reviewed 2026-11-12:

- [OpenAI: Add UI to your MCP server](https://developers.openai.com/plugins/build/chatgpt-ui)
- [OpenAI: MCP server and UI quickstart](https://developers.openai.com/plugins/build/app-quickstart)
- [MCP Apps SDK source and package](https://github.com/modelcontextprotocol/ext-apps)
- Installed version 2.0.4 type declarations for `App`, `AppBridge`, and their
  standard transport and host-context APIs.

These sources inform the adapter design. They do not demonstrate that a specific
ChatGPT account permits the intended connection or that the intended preservation
content is eligible for distribution.
