# Validation and Release Evidence

## Local checks

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

Tests use synthetic temporary files. Coverage includes archive preservation,
bounded ZIP intake, experimental mapping interpretation, branch and identity
invariants, persisted-catalog validation, selective recovery, binary corruption,
query bounds, and consent refusal before selected-content access.

The core has no third-party runtime dependency. The optional MCP and JSON Schema
checks are skipped when their dependencies are absent. To exercise the complete
development integration on Python 3.12, install the recorded dependency set and
run the focused checks:

```bash
python -m pip install -c requirements/chatgpt-dev-py312.constraints.txt '.[chatgpt]'
PYTHONPATH=src python -m unittest tests.integration.test_chatgpt_adapter tests.integration.test_catalog_schema -v
```

The constraints file records the tested Linux/Python 3.12 development environment.
It is not a universal cross-platform lock or a claim that every package is the
newest available release. The adapter uses the official `mcp` SDK as an optional
dependency; upstream code is not vendored. A deployment requires its own update
and security review. The ordinary four-platform core matrix does not install it.

The SDK tests use real MCP client/server sessions and an in-memory Streamable
HTTP transport. They do not establish a live connection to a ChatGPT account.
Schema tests validate generated full, selected, associated, and unsupported
collections; runtime validation additionally enforces cross-record invariants.

## CI configuration

The workflow runs behavioral tests on Linux and Windows with Python 3.11 and
3.14, plus the optional MCP and collection-schema checks on Linux/Python 3.12.
Actions are pinned to reviewed immutable commit identifiers, workflow
permissions are read-only, and checkout does not retain its token in Git
configuration. The workflow performs validation only.

A committed workflow is configuration, not evidence of a successful remote run.
Record the actual run URL, commit, job status, and relevant failures after GitHub
executes it. Local success does not establish Windows success.

## Engineering review

Typed annotations, a standard-library-only core, explicit optional integration
dependencies, and tests support review; they do not prove the entire Golden
Coding Standard automatically.
Static type checking and additional lint tools may be introduced after a pinned
development dependency policy is adopted.

## Release record

Each release should state:

- Exact source commit and toolchain.
- Supported inputs and operating systems.
- Tests and fault scenarios actually executed.
- Benchmark environment, dataset, methodology, and observed limits.
- Legal/consent version and deployment-specific data-handling behavior.
- Known gaps and capability claims excluded from that release.

No test or benchmark report can certify legal enforceability or complete
coverage of a user's account.

See the [collection verification record](collection-verification.md) for the
0.2.0 evidence and the [foundation record](foundation-verification.md) for the
historical 0.1.0 results. Reproduce the semantic workload with the
[collection benchmark](../../benchmarks/COLLECTION_BENCHMARK.md).
