# Private pilot validation record

**Project:** LPX Keepmorrow

**Publisher:** Lopix Neural Inc.

**Engineering lead:** Fabio de Sousa Lopes

**Evidence date:** 2026-11-12

**Release:** 0.3.0 reference service

**Status:** Complete hosted CI matrix passed; live integration and release gates remain open

This record separates implemented and locally exercised behavior from evidence
that requires the intended deployment host, identity provider, ChatGPT account,
or a user-authorized representative export. Passing synthetic tests is not a
substitute for those observations.

An open-source transition is planned. The release license has not yet been
selected or adopted, and the current source license remains in effect. Source
publication is a separate decision from deploying or connecting the service.

The later [source comment review](source-comment-review.md) records the current
comment/docstring validation and regenerated distribution. Artifact hashes and
executed results below remain evidence for their named earlier builds and runs;
they are not silently reassigned to the new wheel or generated HTML.

## Complete hosted CI matrix

[Workflow run 43247833522](https://github.com/fabiocnd/lpx-keepmorrow/actions/runs/43247833522)
completed successfully for commit
`f7cc7dcadc0b19f2f777b0887a63e491539b4a3e`. All **six jobs passed**. The workflow
metadata and each job's decoded log were inspected; the table reports executed
tests separately from skips.

| Job and exact runtime | Recorded result |
| --- | --- |
| Ubuntu, CPython 3.11.18 | 331 discovered; 276 passed, 55 skipped; 4.937 seconds |
| Ubuntu, CPython 3.14.10 | 331 discovered; 276 passed, 55 skipped; 5.636 seconds |
| Windows Server 2025, CPython 3.11.9 | 331 discovered; 273 passed, 58 skipped; 54.488 seconds |
| Windows Server 2025, CPython 3.14.10 | 331 discovered; 273 passed, 58 skipped; 35.843 seconds |
| Complete optional service, CPython 3.12.16 | 331 passed, zero skips; 6.530 seconds |
| MCP Apps interface, Node.js 24.22.2 and npm 11.19.1 | 28 interface tests passed, zero skips, in 1.929308 seconds; eight Playwright synthetic-host tests passed in 30.7 seconds |

Python compilation, canonical policy comparison, private wheel construction,
TypeScript checking, and bundled-asset comparison also passed in their
respective jobs. The Windows logs did not contain the previously observed
unclosed-database warning. Standard-library jobs intentionally omit optional
service dependencies; the complete optional-service job executes those checks.

This run establishes the configured matrix for the named commit. A subsequent
documentation commit requires its own run record if its CI outcome is reported.
Successful synthetic tests do not establish a live ChatGPT connection, a
deployed identity provider, representative-export completeness, or a production
capacity envelope.

## Recorded local validation

The final local source validation used CPython **3.12.14** on **Linux**. Tests use
isolated temporary storage and synthetic data; no real customer export or
connected-account credentials are fixtures.

| Check | Recorded result | Evidence boundary |
| --- | --- | --- |
| Complete Python suite with optional service dependencies | 331 tests passed, zero skips, 5.297 seconds | Local Python behavior, including optional integration tests |
| Fresh standard-library-only environment | 331 discovered; 276 executed, 55 skipped; successful in 3.044 seconds | Core import and test separation without optional service dependencies |
| Python compilation | `src`, `tests`, and `benchmarks` compiled successfully | Syntax and bytecode compilation |
| UI test suite | 28 tests passed, 2.147 seconds | The package's executed DOM and component tests |
| Focused operation and workspace suites | 49 tests passed, 1.220 seconds | Lifecycle, ownership, publication, restart, and application regressions described below |

The complete Python and compilation commands were:

```sh
PYTHONPATH=src python -m unittest discover -s tests -q
python -m compileall -q src tests benchmarks
```

The standard-library check used a fresh virtual environment created with
`--without-pip` and no package installation. The check confirmed that `mcp`,
`starlette`, `jwt`, `cryptography`, `httpx`, and `uvicorn` were absent. To reproduce
that check from the repository root on a POSIX host:

```sh
python -m venv --without-pip .venv-core
PYTHONPATH=src .venv-core/bin/python -m unittest discover -s tests -q
```

The 55 skips are part of the result; optional integration tests did not execute
without their dependencies. Run `npm test` from `ui/chatgpt` for the UI suite and
follow its [build and validation instructions](../../ui/chatgpt/README.md).
Browser execution was not completed locally. Hosted synthetic browser evidence
is recorded separately below.

## Synthetic HTTP pilot

On **November 12, 2026**, the installed 0.3.0 wheel was started on Linux with
CPython **3.12.14** in a newly initialized synthetic operator instance. The
[HTTP smoke runner](../../tests/smoke/run_private_portal.py) completed **16
behavioral checks** over a real loopback TCP socket, then shut down its owned
service with exit code **0**. The complete
[sanitized result](evidence/2026-11-12-loopback-pilot.json) records the runner
digest, distribution digest, exact fixture hashes, outcomes, and limitations.

The workflow exercised the public portal HTTP contracts for login, scoped
acceptance, upload, exact-plan review, idempotent start, import, browse/search/read,
verification, selected recovery, packaging, download, ancestor revocation, and
logout. It used no database shortcuts. Acceptance and review gestures were
synthetic fixtures; they do not represent the owner's human or legal acceptance.

| Observation | Recorded result |
| --- | --- |
| Workflow HTTP responses | 62: 40 HTTP 200, one 201, three 400, two 401, and sixteen 403 |
| Refusal cases | Anonymous session, missing upload/download scope, false acceptance, reused challenges, unreviewed start, revoked ancestor, and ended session |
| Input | Four synthetic conversations in a 3,840-byte ZIP |
| Selected recovery | One conversation, six verified payload files, 19,903-byte delivery ZIP |
| Binary evidence | Exact 70-byte PNG and two opaque binary fixtures of 29 and 32 bytes |
| Service lifecycle | Bounded readiness check, real HTTP transport, graceful owned-child shutdown |
| Existing-state guard | A repeat invocation was refused before launching the service or running maintenance |
| Observed workflow duration | 0.493393 seconds; a functional smoke observation, not a performance benchmark |

The input SHA-256 was
`d763703d5f34cf75a56402954ee9feed16caa0739d3c2d60965dd7ba608c89b3`.
The delivery SHA-256 was
`d59e890ce5bd47c14dbdc1f9360f128a3f91cf62562444bf4136776e52990e84`.
Every enclosed file was checked against the enclosed manifest, and the selected
image/binary payloads were compared directly with their generated inputs. The
GLB/APK-named fixtures are opaque test bytes, not functional models or applications.

Import, recovery, and packaging correctly reported `partial` for intentional
fixture coverage gaps: unknown associations, unresolved artifacts, unsupported
records, and selected omissions as applicable. These outcomes preserve the
distinction between successful byte handling and complete semantic coverage.

The installed wheel digest was
`2fb3b7552a93b728e95b8d928a160e60118c881c8e90f60bb7d4064faf765c0b`;
57 packaged files matched the maintained source with zero mismatches. Production
modules, policies, and UI assets were unchanged by this pilot. The new CI step
initializes a separate instance and retains only its sanitized JSON result.

The child service was stopped after verification. This test does not leave a
public endpoint or persistent deployment running. It does not exercise a browser,
live OAuth, the actual ChatGPT host, or real user content. The
[runbook](../operations/private-service-runbook.md#reproduce-the-synthetic-http-pilot)
contains the reproducible commands and the Linux child-launch restriction.

### Hosted HTTP pilot confirmation

[Workflow run 43256899441](https://github.com/fabiocnd/lpx-keepmorrow/actions/runs/43256899441)
completed successfully for commit
`1a1783144849245a9574e4958054c10d73b3e271`; all six jobs passed. The optional
service job executed all 331 Python tests in 8.236 seconds, then completed the
new HTTP pilot with the same runner digest and all 16 checks passing. Its child
service shut down gracefully. The observed HTTP workflow duration was 0.61027
seconds, and the job retained the sanitized `keepmorrow-synthetic-http-evidence`
artifact. These are results for the named commit, not a claim about any later
documentation commit or a deployed service.

### Application-service fixture synchronization

[Workflow run 43263331539](https://github.com/fabiocnd/lpx-keepmorrow/actions/runs/43263331539)
executed documentation commit `89a7eec307dde46e99e92fb324b182ee7fad72fd`.
Five jobs passed, including the authenticated service and HTTP pilot. The
Windows/Python 3.14 job discovered 331 tests with 58 skips and one error in
40.060 seconds. The completed-lineage test attempted a content read before the
preceding executor had finished workspace cleanup, correctly receiving
`OperationBusy` from the service.

The isolated, serial application-service fixture now waits for both successful
terminal status and zero retained operation reservations within its existing
monotonic deadline. Completion is a publication fact; executor return is the
resource-release boundary. This correction does not change production admission,
authorization, cleanup, or worker ownership. Existing event-controlled lifecycle
tests cover completion before cleanup and retained reservations after cleanup
failure.

The focused correction check passed all **32 tests** in **1.200 seconds** on
local CPython 3.12.14/Linux with this command:

```sh
PYTHONPATH=src python -m unittest \
  tests.integration.test_application_service \
  tests.integration.test_operations_lifecycle \
  tests.integration.test_operations_workspaces -v
```

This local result does not replace the correction commit's hosted Windows check.

## Authenticated ChatGPT setup checkpoint

An authenticated account was observed on November 12, 2026 with the option to
add a custom MCP server. The creation form accepted the project name and
description and offered HTTPS or Tunnel connections with OAuth. The form is an
unfinished browser draft: no server URL or tunnel identity was supplied, and
the plugin was not created, installed, or invoked. Account identity, session
information, and screenshots are excluded from repository evidence.

This observation confirms access to the setup interface. It does not establish
server discovery, user authorization against a live issuer, MCP calls, or
embedded UI behavior. A reachable service and compatible OAuth configuration
remain prerequisites for those tests.

## Historical initial CI and fixture correction

[Workflow run 43244942226](https://github.com/fabiocnd/lpx-keepmorrow/actions/runs/43244942226)
executed source commit `fed82b5eddd4cd6235187d6fd688ac3d079aa5d4`. The job logs
establish these results:

| Job | Recorded outcome |
| --- | --- |
| Ubuntu, CPython 3.11.18 | 331 discovered; 55 skipped; successful in 5.456 seconds |
| Ubuntu, CPython 3.14.10 | 331 discovered; 55 skipped; successful in 3.310 seconds |
| Complete optional service, CPython 3.12.16 | 331 passed; zero skips; 8.078 seconds; policy comparison and wheel build passed |
| MCP Apps interface, Node 24 | Type checking and bundle comparison passed; 28 interface tests passed with zero skips; eight Playwright synthetic-host tests passed in 28.1 seconds |
| Windows Server 2025, CPython 3.11.9 | 331 discovered; 58 skipped; one fixture-cleanup error; 35.003 seconds |
| Windows Server 2025, CPython 3.14.10 | 331 discovered; 58 skipped; the same fixture-cleanup error; 39.718 seconds |

Both Windows jobs exposed an open connection in the foreign-database rejection
test. Python's SQLite connection context commits or rolls back a transaction;
it does not close the connection. Windows therefore refused to delete the
fixture file during temporary-directory cleanup. Python 3.14 also reported the
unclosed connection as a resource warning.

The test now explicitly commits and closes its independent fixture connection
before the existing refusal and byte-preservation assertions. The five access
persistence tests passed locally after this correction. Production modules and
the benchmark source remain unchanged. The corrected Windows results are
recorded in the next section; this first-run failure remains part of the
verification history.

All 49 operation and workspace tests passed in each original Windows job. The
58 skips comprise 55 optional-dependency checks and three platform conditions:
unavailable named pipes, a case-insensitive filesystem that cannot construct the
collision fixture, and the POSIX permission/link contract.

## Historical corrected CI checkpoint

[Workflow run 43245680709](https://github.com/fabiocnd/lpx-keepmorrow/actions/runs/43245680709)
executed commit `9cadba7aa692410e9d99fd7d3483a8a1f350295f`, including the explicit
fixture-connection close. At **2026-11-12 15:19 UTC**, five jobs had completed
successfully. The Ubuntu/Python 3.11 job was marked in progress after runner
assignment but exposed no executed steps. It is not recorded as a passing job
or a test failure.

| Job | Recorded corrected-run outcome |
| --- | --- |
| Ubuntu, Python 3.11 | Awaiting runner steps at this checkpoint; no test result available |
| Ubuntu, CPython 3.14.10 | 331 discovered; 55 skipped; successful in 4.751 seconds |
| Windows Server 2025, CPython 3.11.9 | 331 discovered; 58 skipped; successful in 53.181 seconds |
| Windows Server 2025, CPython 3.14.10 | 331 discovered; 58 skipped; successful in 39.890 seconds |
| Complete optional service, CPython 3.12.16 | 331 passed; zero skips; 6.477 seconds; policy comparison and wheel build passed |
| MCP Apps interface, Node 24 | Type checking and bundle comparison passed; 28 interface tests passed with zero skips; eight Playwright synthetic-host tests passed in 21.7 seconds |

Neither corrected Windows log contained the previous unclosed-database warning.
The Ubuntu/Python 3.11 success in the initial run is evidence for its separately
identified commit; it does not substitute for the pending job. Any later run
must be recorded against its own commit and inspected outcomes. A documentation
commit does not retroactively expand this checkpoint.

### CI scheduling boundary

The corrected Ubuntu/Python 3.11 runner remained in progress with zero reported
steps for more than ten minutes and retained the legacy workflow concurrency
group. The workflow's group was migrated from the old reference-core namespace
to a versioned preservation-service namespace. Branch-level cancellation remains
enabled within the new group. All six jobs, their commands, assertions, platform
matrix, dependency pins, and timeouts remained unchanged. The complete matrix
recorded above provides the subsequent execution evidence.

## Synthetic browser artifact review

Retained screenshots from the initial hosted browser run were visually reviewed
at **1280 × 1600** and **320 × 1600** pixels. The interface remained intact in
both captured views, with no visible horizontal overflow. This review covers
those synthetic-host states and viewport sizes. The executed browser tests and
screenshots do not establish a live ChatGPT connection, external identity-provider
configuration, or the behavior of an unreviewed deployment.

## Operation and workspace evidence

The focused operation and workspace command was:

```sh
PYTHONPATH=src python -m unittest \
  tests.unit.test_operations \
  tests.integration.test_operations_lifecycle \
  tests.integration.test_operations_workspaces \
  tests.integration.test_operations_application -v
```

These suites are included in the complete Python result above. Their scenarios
include authorization ancestry, registration/completion interruption, and
retention ordering.

| Exercised property | Evidence |
| --- | --- |
| Immutable reviewed parameters | Canonical digest binds principal, grant/receipt/version, generation, input digest, selection, and reservation |
| Human decision boundary | Starting without a recorded review fails; model-style `accepted=True` is not an accepted API argument; review replay cannot mint authorization |
| Capture identity | Concurrent idempotent start resolves to one job; conflicting key reuse fails; a fresh review and key preserve another identical-byte capture event |
| Ownership and limits | Foreign plans/jobs/cursors are unavailable; bounded queues, byte reservations, typed metadata, and result categories are enforced |
| Responsive control | Cancellation and status remain usable while a synthetic executor is blocked; shutdown timeout retains exclusive ownership |
| Resource lifetime | Completed status does not release an executor's reservation early; cleanup ambiguity retains capacity and stops claims |
| Actual process interruption | A child process exits before authorization, after authorization, after filesystem publication, and after completion but before release |
| Restart reconciliation | Existing bytes are independently verified against the committed manifest; absence, corruption, and unexpected digest cannot become success |
| Attempt fencing | Old attempts cannot authorize or complete after another attempt owns the operation; retry count is bounded |
| Revocation race | Real AccessStore and OperationStore transactions exercise both commit orderings of revocation and publication authorization |
| Derived access | Disclosure requires current explicit access for each exact ancestor scope; a child grant alone cannot restore revoked or expired source access |
| Temporary containment | Archive staging, ZIP extraction, packing, and unpacking use the exact owned operation directory |
| Conservative cleanup | Matching ledger and marker are required; unknown directories and original sources remain untouched; another filesystem is rejected |
| Output/registry recovery | A registered publication interrupted before completion is verified and discovered after restart |
| Retention ordering | An expired registered package is reconciled before maintenance removes its publication evidence |

No test in this record establishes host power-loss durability, a live browser
login, delivery inside the user's ChatGPT account, or the completeness of an
actual supplied export. Windows support must be assessed from its own CI result,
not inferred from a Linux pass.

## Distribution artifact check

The wheel was built without dependency resolution, build isolation, or package
index access, using setuptools **84.2.1**. Its 50 Python modules matched the
source files. The 64-entry artifact included the canonical policies, bundled
interface, third-party notices, and portal assets. An isolated installation
passed version/resource checks and CLI initialization/configuration validation;
the generated operator key was private and was not printed.

| Artifact | Recorded value |
| --- | --- |
| Filename | `lpx_keepmorrow-0.3.0-py3-none-any.whl` |
| Size | 341,831 bytes |
| SHA-256 | `2fb3b7552a93b728e95b8d928a160e60118c881c8e90f60bb7d4064faf765c0b` |

This is an installation and packaging check, not a public package release. A
change to packaged source, policies, notices, or assets requires a new build and
artifact record.

The source-archive inventory was separately reviewed: **189 files**, excluding
Git repository metadata/history, removed private development records, and local
credentials or runtime state. Local file targets in **54 Markdown documents**
resolved successfully. These are artifact-structure and documentation-link
checks; they do not constitute a repository-history purge or a new source
license. Rebuild the source archive after the final documentation commit. Its
digest must describe those final bytes rather than this intermediate inventory.

## Local service benchmark

The [private service benchmark](../../benchmarks/PRIVATE_SERVICE_BENCHMARK.md)
and its [raw result](../../benchmarks/results/2026-11-12-private-service-reference.json)
record three synthetic workflows with 250 conversations, 3,000 graph nodes, an
8 MiB binary, and one content worker. Each workflow covered upload, import,
selected recovery, packaging, download, and unpacking through direct application
service calls. Source bytes did not change during the run; the benchmark records
their aggregate digest.

Observed workflow times were **1.800037**, **1.974448**, and **1.957537 seconds**.
The child process's cumulative peak RSS was **34,865,152 bytes**. Across 113
active control observations, median status latency was **2.424 ms** and median
metadata-list latency was **2.455 ms**; observed maxima were **234.812 ms** and
**103.333 ms**, respectively. The largest sampled scratch inventory was
**27,487,694 logical bytes**, and the final scratch inventory was empty.

These observations include fixture and sampling effects. The storage sampler
can miss short-lived files, and its maximum is not a proven peak. The benchmark
does not exercise HTTP, OAuth, a browser, a ChatGPT account, or a cold filesystem.
It establishes neither a deployment capacity limit nor a latency commitment.
Use the benchmark's methodology and complete measurements when interpreting
these results.

## Operating envelope to measure on the selected host

The reference service defaults to a 128 MiB upload ceiling, a 512 MiB archive
payload ceiling for connected operations, a 2 GiB declared reservation per
operation, one content worker, and a 4 GiB managed-storage budget. The transfer
container has its own encoded and expanded limits. These are rejection ceilings
and conservative reservations, not measured throughput or capacity promises.

Configuration enforces `upload_pool_bytes = 4 * max_upload_bytes` and requires
`max_storage_bytes >= upload_pool_bytes + 2 GiB` to admit at least one declared
operation reservation. Default 128 MiB uploads require at least **2.5 GiB** of
configured managed storage; a 1 GiB upload ceiling requires at least **6 GiB**.
Retained outputs and further queued reservations consume the remaining budget.
Actual filesystem capacity and metadata growth require separate monitoring.

For each candidate host, record its CPU, memory, filesystem, disk quota, Python
and dependency versions, exact repository commit, configuration, and dataset
inventory. Use synthetic workloads first, then a separately authorized export.
Measure cold and warm runs rather than reporting one favorable sample.

| Workload | Measurements and expected boundary |
| --- | --- |
| Many small files | Process RSS, path/entry counts, temporary bytes, import and verification elapsed time |
| Large binaries | Streaming buffer behavior, total I/O, peak temporary storage, cancellation latency |
| Dense conversation metadata | Decode/parse time, node/edge/text limits, peak RSS, explicit rejection before publication |
| Repeated captures | Generation growth, retained-output accounting, source identity/provenance retention |
| Queue saturation | Admission response time, global/principal limits, fixed busy outcomes, no lost idempotency |
| Read during active work | Status/cancel latency and content-I/O busy behavior; no unbounded background task accumulation |
| Interrupted process | Each publication boundary, workspace cleanup, output verification, stable intended output ID |
| Disk exhaustion | Failure category, staging ownership, no source modification or false completion |
| Transfer interruption | Upload expiration/pins, partial-file cleanup, authenticated download revalidation |
| Expired/revoked access | Rejection before processing, ancestor checks, publication ordering, blocked subsequent disclosure |
| Backup and rollback | Consistent snapshot recovery, verified generations, preserved revocations, recovery point/time |

A deployment p95 control-latency target remains a proposal until measured on
that host. JSON parsing and individual system calls can delay cooperative
cancellation. Publish the observed distribution and its limitations rather than
claiming a universal cancellation deadline.

## Remaining release gates

| Gate | Required evidence | Current evidence boundary |
| --- | --- | --- |
| Live ChatGPT distribution path | Account/plan capability, developer setup, private connection, resource rendering, actual tool behavior | Authenticated creation interface verified; endpoint discovery, creation, installation, rendering, and tool calls remain unverified |
| Live identity provider | Registered clients, PKCE/browser flow, issuer/audience/JWKS validation, token expiry/rotation, session behavior | Synthetic verifier and protocol tests do not prove a deployed provider configuration |
| Actual binary transfer | Host-supported upload selection and one authenticated output downloaded and independently verified | Local byte round trips are available; host-specific delivery must be observed |
| Representative export | Explicit intake/review consent, inventory, actual images/binaries and missing-artifact report, branch/association findings | No user-authorized representative archive was supplied for this validation |
| Browser visual review | Consent readability, keyboard/focus behavior, and actual host iframe behavior | Eight hosted synthetic tests passed; desktop and narrow screenshots were reviewed without visible horizontal overflow; live host behavior remains unverified |
| Deployment envelope | Measured RSS/storage/I/O, load rejection, dependency failures, retention, restart, backup/rollback on selected host | No production host or load envelope has been qualified |
| Legal release review | Correct entity/jurisdiction facts, operative privacy/retention disclosures, review of mandatory rights and liability limitations | Draft policy text and enforced acceptance do not establish legal enforceability |
| Open-source publication | Adopted release and contribution terms, complete third-party attribution, reviewed release contents, and an explicit publication decision | The transition is planned; no replacement source license or public release is established by this validation |

The repository and pilot remain private under their current terms. Resolve the
applicable gates with concrete evidence before publication, deployment, or a
claim that the integration operates in a particular ChatGPT account. A source
release does not by itself establish production readiness.

Related documents: [delivery plan](../architecture/chatgpt-delivery-plan.md),
[operation journal](../architecture/operation-journal.md),
[private service runbook](../operations/private-service-runbook.md),
[Golden Coding Standard](golden-coding-standard.md), and
[Performance Policy](performance-policy.md).
