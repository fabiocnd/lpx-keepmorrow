# Keepmorrow MCP Apps Interface

**Publisher:** Lopix Neural Inc.
**Engineering lead:** Fabio de Sousa Lopes
**Contact:** fabio@lopixneural.com
**Status:** Implemented interface; local protocol/DOM tests and remote Chromium synthetic-host tests passed; actual ChatGPT host validation pending

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

Project-owned source uses Apache License 2.0. The UI package keeps `private: true`
to prevent accidental npm publication, not to restrict source rights. Its manifest
and lockfile declare `Apache-2.0`. THIRD-PARTY-NOTICES.txt is generated from the
packages that contribute bytes to the bundle and retains their complete installed
license texts, including the MCP transition notices. Development dependencies
remain identified in the lockfile, not included in the production HTML.

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

Observed locally on 2026-11-12 with Node.js 24.22.1:

| Check | Observed result |
| --- | --- |
| Strict TypeScript and bundle build | Passed |
| 28 contract, DOM, portal, and SDK protocol checks | Passed |
| Eight Playwright cases | Blocked before page launch: Chromium profile socket creation was denied by the executor |
| Command retry outside the sandbox | Rejected by the environment's approval policy; sandbox escalation was unavailable |
| Managed browser preview | The browser could not reach the executor's local preview; the resulting error page was then blocked by browser URL policy |
| Actual authenticated ChatGPT host | Not tested in this implementation environment |

The local launch restriction remains a recorded environment limitation. It is
not represented as a passing or skipped local run. The later remote execution
below establishes a separate browser result.

### Remote browser qualification

The [MCP Apps interface CI job](https://github.com/fabiocnd/lpx-keepmorrow/actions/runs/43244942226/job/131274965761)
completed on November 12, 2026, for commit
`fed82b5eddd4cd6235187d6fd688ac3d079aa5d4`. The Ubuntu 24.04 runner used
Node.js 24.22.2 and Chrome for Testing 158.0.8127.18 through Playwright 1.65.0.
Inspected logs recorded:

- A successful strict TypeScript build and a byte-identical 689,499-byte packaged
  HTML resource.
- All 28 contract, DOM, portal, and SDK protocol checks passed.
- All eight real-Chromium Playwright cases passed in 28.1 seconds using the
  official SDK synthetic host.
- Two synthetic screenshots were uploaded as
  `keepmorrow-synthetic-browser-evidence`, artifact ID `13954849464`.

The 184,926-byte artifact ZIP was downloaded and checked against GitHub's SHA-256:
`77e00e4d000c4ff9f000c5f7d791fc20dd02497252f9f5bb6250077f737fd781`.
The 1280 × 1600 desktop and 320 × 1600 narrow screenshots were visually reviewed.
The captured controls remained separated and readable; the narrow view wrapped
the deliberately long source title and stacked controls without horizontal
overflow. These captures are synthetic examples, not account data. The CI
artifact has the workflow's 14-day retention period.

This result qualifies the tested companion interactions and synthetic browser
transport on that runner. It does not establish an actual ChatGPT connection,
all-browser support, a complete accessibility audit, or rendering-performance
targets. The trusted portal's real-browser authentication and file-transfer flow,
plus the actual authenticated ChatGPT interface and delivery path, remain release
evidence to collect in the selected deployment.

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
