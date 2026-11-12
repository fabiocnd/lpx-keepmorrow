# Validation and Release Evidence

**Applies to:** The private 0.3.0 implementation

**Review date:** 2026-11-12

Validation distinguishes preservation correctness, service authorization,
operational recovery, interface behavior, live host compatibility, and measured
capacity. Each result must identify the source revision, toolchain, command,
executed checks, skips, and material limits.

## 1. Python core and optional service

From the repository root, with Python 3.11 or later:

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
python -m compileall -q src tests benchmarks
```

PowerShell:

```powershell
$env:PYTHONPATH = "src"
python -m unittest discover -s tests -v
python -m compileall -q src tests benchmarks
```

The preservation core, catalog, access metadata, operation journal, and transfer
contracts use the standard library. Optional HTTP/MCP, JWT, and JSON Schema
tests explicitly skip when their dependencies are unavailable. Validate this
separation in a fresh environment created without package installation; record
the skips instead of describing the optional checks as passed.

For the complete optional Python service on the recorded Linux/Python 3.12
development environment:

```bash
python -m pip install -c requirements/chatgpt-dev-py312.constraints.txt '.[chatgpt]'
PYTHONPATH=src python -m unittest discover -s tests -v
python -m compileall -q src tests benchmarks
```

The constraints file records the selected dependency closure. It is not a
cross-platform deployment lock or a claim that every package is the newest
available version. The official MCP SDK and other optional dependencies are
installed packages; the project does not patch upstream code to pass tests.
Review dependency and license changes with the application change they support.

The behavioral suite includes byte preservation, bounded ZIP/JSON/catalog
intake, explicit association uncertainty, selected recovery, identity isolation,
human acceptance/review, idempotency, publication/revocation ordering, process
interruption, cleanup ownership and ledger failures, displayed consent-expiry
binding, binary transfer, authorization ancestry,
retention, portal boundaries, and the SDK's MCP transport. Synthetic fixtures
keep these checks reproducible without private customer material.

SDK and in-process HTTP tests do not exercise a live ChatGPT account, external
identity provider, public reverse proxy, or actual host file picker. Generated
schema validation also does not replace the runtime's cross-record integrity
checks. The current evidence is recorded in
[Private Pilot Validation](private-pilot-validation.md).
The subsequent [consent and cleanup record](consent-cleanup-verification.md)
identifies the targeted regression evidence and its source boundary.

## 2. Policy assets and private wheel

Canonical legal drafts live in `legal/`; package copies are generated from
those bytes. Rebuild and inspect them when policy text changes:

```bash
python scripts/build_policy_assets.py
git diff --exit-code -- src/keepmorrow/policies
python -m pip wheel --no-deps . --wheel-dir dist
```

In a development edit, review and include the intended generated-policy diff
before expecting the comparison to pass. In a clean release checkout, a changed
copy indicates that the committed package assets are stale. Verify that a built
wheel contains the required policy and interface assets; a successful wheel
build alone does not demonstrate that an installed service can use them.

Acceptance binds exact policy versions and document digests. Updating words
without changing a version still changes the digest and requires new applicable
acceptance. A legal document's inclusion in a tested wheel does not establish
its enforceability or authorize a public release.

## 3. Interface validation

From `ui/chatgpt`, using the recorded Node 24 environment:

```bash
npm ci --ignore-scripts
npm run build
npm test
npm run test:browser
```

The build checks TypeScript and regenerates the bundled HTML and third-party
notices. The test commands cover different evidence: bounded message contracts,
DOM behavior, trusted-portal interactions, official SDK behavior, and a separate
Playwright synthetic browser host. Follow the
[UI package instructions](../../ui/chatgpt/README.md) to install a supported test
browser and inspect its current results and execution restrictions.

A blocked or unexecuted browser run is not a pass or an intentional test skip.
Review screenshots, keyboard/focus behavior, consent readability, and actual
host iframe behavior separately. A synthetic browser host does not establish
successful rendering inside the user's ChatGPT account.

## 4. CI configuration and actual remote evidence

The committed workflow defines these jobs:

| Job group | Configured checks |
| --- | --- |
| Ubuntu and Windows, Python 3.11 and 3.14 | Four standard-library jobs: syntax and behavioral discovery; optional dependencies remain absent |
| Authenticated service and MCP, Linux/Python 3.12 | Pinned optional dependencies, complete Python discovery, synthetic loopback HTTP workflow, canonical policy comparison, private wheel build |
| MCP Apps interface, Linux/Node 24 | Locked dependencies, TypeScript/build consistency, interface tests, Playwright synthetic host, retained browser evidence |

Actions are pinned to immutable commit identifiers. Workflow permissions are
read-only, and checkout does not retain its token in Git configuration. The
workflow validates and retains private build/evidence artifacts; it does not
deploy a service or submit a public ChatGPT directory listing.

Configuration is separate from execution. Record each actual run URL, exact
source commit, job outcome, passed/skipped/failed checks, and any inspected
artifact. Local Linux success does not establish Windows success. A later
documentation commit does not expand an earlier run's source or platform scope.

## 5. Review and release acceptance

The [Golden Coding Standard](golden-coding-standard.md) requires typed and
validated boundaries, coherent ownership, explicit failure states, proportionate
tests, current documentation, and evidence-backed claims. Python annotations
and a passing suite do not automatically enforce the whole standard. The UI
has TypeScript checking; a project-wide Python static type checker and separate
lint gate are not currently configured.

For each release, record:

- The exact source commit, built-artifact identity, and toolchain.
- The supported input profiles, byte/metadata limits, and executed platforms.
- Tests and fault scenarios actually run, including failures and skips.
- Benchmark source/workload, RSS and storage measurement method, variability,
  and the host conditions that limit interpretation.
- Policy versions/digests, operative data handling, retention, and deployment
  boundaries.
- Live integration evidence and the capabilities still unavailable or untested.

Use the [Performance Policy](performance-policy.md) for performance claims and
the [private service runbook](../operations/private-service-runbook.md) for
operational procedures. A local benchmark is not a production capacity
qualification. No software test can certify legal enforceability or complete
coverage of a provider account.

## Historical records

The [0.2.0 collection record](collection-verification.md) and
[0.1.0 foundation record](foundation-verification.md) retain their original
commands, counts, remote commits, CI outcomes, and limitations. They are
historical evidence for those revisions. Current service claims belong in the
private pilot record and the final release evidence, not in rewritten historical
results. The [benchmark index](../../benchmarks/README.md) identifies the separate
archive, collection, and private-service workloads.
