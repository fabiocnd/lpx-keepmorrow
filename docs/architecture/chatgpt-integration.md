# ChatGPT Development Adapter

**Status:** Implemented local MCP protocol adapter; no deployed or installed ChatGPT connection
**Review date:** 2026-11-12
**Owner:** Lopix Neural Inc.
**Engineering lead:** Fabio de Sousa Lopes

## Intended user experience

The product is intended to be usable from a ChatGPT conversation. OpenAI's current
plugin documentation describes MCP servers that expose tools to ChatGPT and an
optional MCP Apps interface rendered inside the conversation. A custom component
is not required to use tools. The connection uses a configured reachable server
or a supported tunnel, authentication as appropriate, and installation under the
account or workspace's permissions.

Sources reviewed:

- [Build an MCP server](https://developers.openai.com/plugins/build/mcp-server)
- [MCP server and UI quickstart](https://developers.openai.com/plugins/build/app-quickstart)
- [Add UI to your MCP server](https://developers.openai.com/plugins/build/chatgpt-ui)
- [Connect a custom MCP server](https://developers.openai.com/api/docs/guides/custom-mcp-server)

These platform capabilities do not grant unrestricted access to ChatGPT history,
Projects, attachments, or private account data. The adapter can expose only the
collections explicitly granted by its own operator. This repository does not
implement native ChatGPT chat restoration or account enumeration.

## What is implemented

The optional adapter uses the official Python MCP SDK and exports these tools:

| Tool | Behavior |
| --- | --- |
| `list_collections` | Lists configured opaque IDs without opening their collections |
| `browse_collection` | Verifies an allowed collection and returns paginated conversation/revision metadata |
| `search_collection` | Verifies the collection and returns bounded literal-search results |
| `read_revision` | Verifies the collection and returns a bounded page of graph nodes |
| `verify_collection` | Verifies archive bytes and the semantic catalog contract |

Each tool requires exact current terms and privacy versions before resolving a
registered collection or accessing its content. Inputs use opaque IDs rather than
arbitrary filesystem paths. Tool annotations accurately declare read-only,
nondestructive, closed-scope behavior. Results include operation receipts and
fixed public error categories; registered paths and exception strings are not
returned to clients.

The server is bound to `127.0.0.1`, defaults to port `8765`, and uses `/mcp` with
stateless Streamable HTTP and JSON responses. Request bodies are capped at 64 KiB;
structured results are capped at 512 KiB. Pages contain at most 50 primary rows
and 20 revision summaries per conversation. Verification execution is admitted
one at a time with a nonblocking busy response instead of an unbounded work queue.

The standalone archive HTML view is implemented separately. No custom MCP Apps
component, upload picker, binary download endpoint, import tool, or recovery write
tool is exposed by this development adapter.

## Development setup

The local preservation core remains standard-library-only. The optional dependency
is pinned to `mcp==1.29.0`, the SDK version exercised here. Its upstream license is
MIT; see [package metadata](https://pypi.org/project/mcp/1.29.0/) and the
[upstream repository](https://github.com/modelcontextprotocol/python-sdk).
This dependency does not change the proprietary license of Keepmorrow.

The observed Linux/Python 3.12 dependency closure is constrained for the dedicated
CI job in `requirements/chatgpt-dev-py312.constraints.txt`. It is not a universal
deployment lock or a claim that this SDK is the newest release. Dependency and
license review remain part of the eventual hosted release process.

```bash
python -m pip install -c requirements/chatgpt-dev-py312.constraints.txt '.[chatgpt]'
```

Create a private registry outside the repository. Its paths are explicit developer
grants; they are configuration, not tool arguments:

```json
{
  "format": "lpx-keepmorrow.chatgpt-registry",
  "version": 1,
  "collections": {
    "research-archive": "/absolute/path/to/collection-001"
  }
}
```

Use an absolute Windows path with escaped backslashes when running on Windows;
the optional SDK adapter's recorded validation environment is Linux/Python 3.12.
The registry parser rejects duplicate keys, unsupported versions, relative paths,
and path-like IDs. Loading grants does not inspect their selected contents.

```bash
python -m keepmorrow.integrations.chatgpt --registry /absolute/path/to/private-registry.json
```

Use a local MCP client to initialize the connection and call its tools. Supplying
current version strings establishes a local declaration, not proof of an
authenticated person's agreement. The adapter must not be treated as a public
multi-user service merely because it implements HTTP.

## Required before a real ChatGPT connection

The current test adapter intentionally does not supply the following deployment
decisions or capabilities:

1. A selected execution environment and reachable authenticated endpoint or
   supported secure tunnel with reviewed host/origin configuration.
2. Authenticated identity, per-user collection grants, and a deployment-specific
   consent record and privacy disclosure for data returned to the ChatGPT client.
3. User-selected file intake and safe storage destinations, if import/recovery
   actions are to be exposed through ChatGPT.
4. Private installation and acceptance testing in the actual account/workspace.
5. Qualified review of the legal drafts before public use and a separate public
   distribution decision.

Do not weaken the loopback host restrictions or publish an unauthenticated endpoint
as a shortcut. A connected client may display, retain, or process returned
conversation text under its own settings; that disclosure needs a real interface
and authorization design before private user material is connected remotely.

## Observed validation

The adapter tests initialize actual MCP SDK client/server sessions, discover tools,
call them against synthetic collections, and exercise Streamable HTTP through an
in-process ASGI transport. Tests cover acceptance before I/O, opaque grants,
invalid IDs, pagination, private-path error redaction, host rejection, and busy
admission. See the [verification record](../engineering/collection-verification.md)
for the exact source revision and CI outcome.

These checks establish local protocol behavior. They do not establish deployment,
ChatGPT installation, UI rendering in ChatGPT, or account permissions.
