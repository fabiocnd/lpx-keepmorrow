# Private pilot validation record

**Project:** LPX Keepmorrow

**Publisher:** Lopix Neural Inc.

**Engineering lead:** Fabio de Sousa Lopes

**Evidence date:** 2026-11-12

**Release:** 0.3.0 reference service

**Status:** Local reference validation; live release gates remain open

This record separates implemented and locally exercised behavior from evidence
that requires the intended deployment host, identity provider, ChatGPT account,
or a user-authorized representative export. Passing synthetic tests is not a
substitute for those observations.

An open-source transition is planned. The release license has not yet been
selected or adopted, and the current source license remains in effect. Source
publication is a separate decision from deploying or connecting the service.

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
Browser visual execution was not completed locally. No remote CI outcome for
this release is claimed in this record.

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
| Live ChatGPT distribution path | Account/plan capability, developer setup, private connection, resource rendering, actual tool behavior | Documentation and local implementation do not prove this account can connect |
| Live identity provider | Registered clients, PKCE/browser flow, issuer/audience/JWKS validation, token expiry/rotation, session behavior | Synthetic verifier and protocol tests do not prove a deployed provider configuration |
| Actual binary transfer | Host-supported upload selection and one authenticated output downloaded and independently verified | Local byte round trips are available; host-specific delivery must be observed |
| Representative export | Explicit intake/review consent, inventory, actual images/binaries and missing-artifact report, branch/association findings | No user-authorized representative archive was supplied for this validation |
| Browser visual review | Desktop/mobile screenshots, consent readability, keyboard/focus behavior, host iframe behavior | See the UI package's current validation record; DOM tests alone do not establish visual quality |
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
