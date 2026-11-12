# Consent Deadline and Cleanup Failure Verification

**Evidence date:** 2026-11-12

**Release:** 0.3.0 private reference service

**Scope:** Fixed consent-deadline presentation and binding; conservative worker
handling of workspace-cleanup metadata errors

This change resolves the two implementation follow-ups identified in the
[source comment review](source-comment-review.md). The baseline was GitHub
commit `18f1295831b4781185f027c4c6f77363cebdf087`, with source tree
`a2548aa78ff8420e743bdf46d635b77bf2f693c9`. The local baseline had the same tree.
The earlier review's observations and artifact hashes remain historical evidence.

## 1. Consent deadline contract

Preparation already created an administrative grant with a fixed deadline.
The portal now returns that stored `expires_at` value, displays it explicitly in
UTC, and includes it in the same scope declaration used for challenge hashing
and retained acceptance evidence. Presentation does not calculate a replacement
deadline.

Acceptance requires the exact integer timestamp. Within the existing write
transaction, the handler compares the submitted declaration with the current
grant, consumes the matching single-use challenge, creates the receipt with the
reviewed deadline, and records the acceptance context. A delayed confirmation
does not create another one-hour authorization window.

The following requests are refused:

- Missing, modified, Boolean, string, null, or equivalent floating-point expiry.
- An old challenge paired with a changed authoritative grant deadline, even if
  the submitted timestamp matches that newer value.
- Submission at an expired grant or challenge boundary, replay, or use of a
  challenge from a different browser session for the same principal.

Rejection leaves no partial receipt or acceptance context. A rejected field
edit does not consume an otherwise valid challenge. Existing session, origin,
CSRF, policy, grant-version, and explicit-choice requirements remain in force.

The interface rejects missing or unsupported timestamps before opening a new
review and clears any earlier prepared consent. It keeps all four declarations
unchecked for each valid scope. The original integer is retained for submission;
only its presentation is formatted as a UTC date and time.

The authorization deadline is separate from the shorter challenge and browser
session lifetimes. The page explains that sign-in or review may expire earlier.
Older forms without `expires_at` must be reloaded and prepared again. Previously
accepted grants retain their existing deadlines; no persistent schema migration
or legal-policy revision is introduced.

Implementation and contract:
[portal handler](../../src/keepmorrow/integrations/chatgpt/portal.py),
[portal interface](../../src/keepmorrow/integrations/chatgpt/portal_assets/portal.js),
[trusted portal](../architecture/trusted-portal.md).

## 2. Cleanup failure reproduced and corrected

The earlier source-only concern was reproduced before changing the runtime.
The initial ownership-ledger read and final ledger transaction were outside
the cleanup-error classification. An injected metadata error could therefore
reach the ordinary execution-failure path instead of stopping claims and
retaining the executor's ownership hold.

With the unchanged runtime, **four new regressions failed**: read and
precommit-deletion failures, each before and after operation completion. The
workspace module ran 14 tests in 20.152 seconds; its nine existing tests and the
new unexpected-error propagation test passed.

In both postcompletion cases, the affected result remained completed, but
`worker_released` became `1`, the worker continued, and the following queued
job was claimed. The two jobs' expected 2,048-byte total reservation fell to zero
after both were released. Before completion, the affected operation was
classified as ordinary failed execution rather than interrupted cleanup.

`OperationWorkspaces.discard()` now translates `PersistenceError` and raw
`sqlite3.Error` into `OperationCleanupRequired` at both metadata boundaries.
The original cause is preserved. Raw SQLite errors are included because a
transaction's rollback or finalization can report an error outside its usual
persistence translation. Arbitrary `RuntimeError` remains unchanged.

No worker or global persistence-layer change was needed. The existing worker
handler retains `worker_released = 0`, stops new claims, and preserves an already
recorded completed result. For unfinished work, it records interrupted cleanup.
The worker closes its process-lock session after execution unwinds; the
persisted reservation remains for ordered recovery.

### Regression cases and recovery

| Injected boundary | Preserved state and observed recovery |
| --- | --- |
| Initial ownership read | Ledger, exact marker, and temporary payload remain; the worker stops and retains its hold |
| After DELETE, before successful transaction exit | Actual rollback retains the ledger even though the directory was removed; startup retires the proven absent workspace |
| After the deletion transaction already committed | Directory and ledger are absent, but the reported failure still retains the worker hold until startup reconciliation |
| Repeated startup failure | Two startup attempts refuse admission before reconciliation can clear the old execution hold |
| Unexpected `RuntimeError` | The original exception propagates without being reclassified as an expected database failure |

Tests inspect `worker_released` directly because an interrupted operation can
remain counted by its state even after an incorrect executor release. They
also verify that the worker exits before test teardown requests shutdown, the
following job stays queued, and unrelated source bytes remain unchanged.

Once the injected failure clears, cleanup runs under exclusive ownership before
operation reconciliation and subsequent claims. An already absent directory
does not require a replacement marker. An unfinished reconciled operation still
requires an explicit cancellation or authorized retry to resolve its remaining
pending-operation reservation.

This reservation guarantee applies when cleanup errors propagate through worker
execution and startup recovery. Download verification also uses the workspace
helper, but receives the exception at its own boundary and does not acquire the
worker guarantee merely by calling that helper.

Implementation and contract:
[workspace cleanup](../../src/keepmorrow/application/staging.py),
[regression tests](../../tests/integration/test_operations_workspaces.py),
[operation protocol](../architecture/operation-journal.md).

## 3. Executed local validation

Environment: Linux, CPython **3.12.14**, Node.js **24.22.1**, and setuptools
**84.2.1**. Fixtures contain synthetic data only.

| Check | Observed result |
| --- | --- |
| Focused consent and session suite | 26 passed; zero skips; 0.970 seconds |
| Focused portal DOM suite | 15 passed; zero skips; 2.073 seconds |
| Workspace suite after the fix | 16 passed; zero skips; 0.186 seconds |
| Workspace, lifecycle, and journal suite | 53 passed; zero skips; 1.168 seconds |
| Complete Python suite | 342 passed; zero skips; 5.480 seconds |
| Complete interface suite | 29 passed; zero skips; 1.760551741 seconds |
| Python compilation | `src`, `tests`, and `benchmarks` compiled successfully |
| TypeScript checking and normal UI build | Passed; MCP companion HTML remains 690,131 bytes |
| Built wheel inspection | All 57 packaged source/asset files matched the checkout |
| Installed-wheel loopback HTTP workflow | 18 checks passed; owned child shut down with exit code 0 |

The focused commands were:

```sh
PYTHONPATH=src python -m unittest tests.integration.test_portal tests.unit.test_human_sessions -v
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 python -m unittest tests.integration.test_operations_workspaces -v
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 python -m unittest tests.integration.test_operations_workspaces tests.integration.test_operations_lifecycle tests.unit.test_operations -v
```

Complete source and distribution commands from the repository root:

```sh
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -q
python -m compileall -q src tests benchmarks
python -m pip wheel --no-deps --no-build-isolation --no-index . --wheel-dir dist/consent-cleanup
git diff --check
```

From `ui/chatgpt`:

```sh
node --test tests/portal.dom.test.mjs
npm run build
npm test
```

The Python suite emitted the existing Starlette TestClient/httpx deprecation and
Pydantic settings forward-reference warnings. Dependency versions were unchanged.
The hosted workflow attached to the pushed commit supplies its own Windows,
additional Python-version, and synthetic-browser evidence; the local table does
not imply those checks ran locally.

## 4. Installed distribution and HTTP evidence

The wheel was installed without dependency resolution into a fresh virtual
environment using the existing system site packages. Validation removed
`PYTHONPATH`, ran outside the source directory, and confirmed that the imported
`keepmorrow` package came from the new environment. This proves the tested
application came from the wheel; the third-party dependency environment was
shared rather than rebuilt from scratch.

The [sanitized HTTP report](evidence/2026-11-12-consent-cleanup-http.json) records
the runner and distribution hashes, generated input, selected binary recovery,
all 18 results, and clean service shutdown. The new checks refuse an edited
deadline and then accept the original challenge with its unchanged receipt
expiry. The workflow retains the existing upload, exact-plan review, idempotency,
query, recovery, download, revocation, and logout checks.

To reproduce with the intended installed Python interpreter and a fresh private
instance, initialize with `--operator synthetic-pilot` and then run
`tests/smoke/run_private_portal.py --configuration <instance>/service.json
--launch-service`. Use the same interpreter for both commands and keep
`PYTHONPATH` unset when qualifying an installed distribution. Full operating
instructions are in the [runbook](../operations/private-service-runbook.md).

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| `dist/consent-cleanup/lpx_keepmorrow-0.3.0-py3-none-any.whl` | 356,760 | `4e2ac26765bd05fb811c5efa9da66560bd7f9a66bb52388285d909970372ed54` |

The digest identifies this build. Other wheel builds can have different archive
metadata. Earlier distribution hashes remain valid for their earlier artifacts.

## 5. Evidence limits

The metadata regressions inject errors into transaction boundaries. The
precommit fixture executes a real DELETE and then raises before the actual
commit, exercising rollback. The finalization fixture raises after successful
transaction exit. These tests do not induce actual SQLite commit, rollback, or
close failures, physical storage faults, or power loss.

The HTTP pilot uses real loopback transport with synthetic acceptance gestures;
it is not human or legal acceptance and processes no real user export. It does
not establish live OAuth, an actual ChatGPT connection, legal enforceability,
production capacity, or a public source release. No performance benchmark was
rerun, and no throughput or latency improvement is claimed.
