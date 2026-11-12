# Operation journal and publication protocol

**Status:** Implemented reference service component

**Owner:** Lopix Neural Inc.

**Engineering lead:** Fabio de Sousa Lopes

**Review date:** 2026-11-12

The operation journal persists reviewed intent, admission, attempt ownership,
cancellation, and publication decisions in the same SQLite database as access
grants. Its scope is recovery from a stopped process on the configured local
filesystem. It does not establish payload survival after power loss, storage
controller failure, or an inconsistent backup.

The implementation lives in `src/keepmorrow/operations/`. The application owns
content execution, filesystem locations, access callbacks, and output
inspection. The journal never interprets conversations or decides whether an
archive is semantically complete.

## 1. Reviewed operation contracts

| Typed parameters | Required action | Bound input |
| --- | --- | --- |
| `ImportParameters` | `import` | Owned upload handle, input SHA-256, account namespace, optional previous generation |
| `RecoveryParameters` | `recover` | Selected conversation digests or one project; optional revision for one conversation |
| `AssociationParameters` | `associate` | Conversation digest, explicit association state, project identifier when applicable, bounded reason |
| `PackageParameters` | `package` | Exact collection generation in the authorization scope |
| `UnpackParameters` | `unpack` | Owned upload handle and input SHA-256 |

Every plan includes the principal ID, resource ID, exact generation, action,
grant ID and version, acceptance receipt ID, and declared storage reservation.
The canonical versioned JSON representation of these fields and the typed
parameters determines `parameter_digest`. Timestamps and the randomly generated
plan ID do not determine that digest. Recovery selections are sorted before
serialization; duplicate identities are rejected.

Plans are immutable. A changed input digest, selection, generation, grant,
acceptance receipt, principal, or reservation requires a different reviewed
plan. The journal accepts opaque identifiers at path-independent boundaries.
Project identifiers, account namespaces, and association reasons are necessary
bounded parameters; they are not included in operation status responses.

Preparation does not authorize an earlier upload. The application must obtain
intake authorization before receiving or inspecting user-supplied bytes.
`OperationStore.prepare()` records an already authorized plan; it does not
stage content itself.

## 2. Human review and idempotency

`record_human_review()` belongs only to the authenticated human interaction
handler. That handler displays the exact plan, verifies its session and
anti-forgery boundary, and records a positive gesture. No model-callable tool
accepts a substitute `accepted` boolean. A Python method signature cannot prove
that a human acted; correct placement of this writer remains an application
security obligation.

Each review binds a principal, plan, parameter digest, interaction ID, and
expiration. An interaction replay returns its existing review and cannot mint
another authorization. One review authorizes one new operation. Reusing the
review for another idempotency key fails unless another deliberate human review
has been recorded.

Idempotency keys are scoped to the principal across operation kinds. The
journal stores the SHA-256 of the bounded key. The same principal, key, and
canonical parameters return the existing operation, including its terminal or
interrupted state. Different parameters under that key fail. A new key and a
fresh review can create another capture with identical source bytes; capture
identity is not deduplicated by source fingerprint.

An idempotent replay does not retry an interrupted job. `retry()` is a separate
trusted operation that requires successful reconciliation, fresh access,
available attempts, and an unexpired review for the same job or a newly recorded
review. An expired plan requires new planning. There is no unbounded automatic
retry or per-file continuation.

## 3. Admission and metadata bounds

| Default journal ceiling | Value |
| --- | --- |
| Pending operations across principals | 16 |
| Pending operations per principal | 4 |
| Unexpired prepared plans per principal | 32 |
| Declared pending/live-executor reservations | 4 GiB |
| One operation reservation | 2 GiB |
| Canonical plan document | 16 KiB |
| Result document | 4 KiB |
| Attempts per operation | 3 |
| Plan lifetime | 3,600 seconds |
| Review lifetime | 900 seconds, capped by plan expiration |
| Status page | At most 100 operations |
| Explicit recovery conversation selection | At most 100 identities |

The application may select lower ceilings. Reservations are admission estimates,
not filesystem quotas. Executors must independently enforce actual archive,
upload, extraction, and package byte limits. An optional `start(..., admit=...)`
callback can combine retained output accounting with `reserved_bytes()` using
the same transaction. The service reserves its entire upload pool separately
because the upload ledger is a different database.

Pending jobs, interrupted jobs, and terminal jobs whose executor has not
returned remain reserved. A persisted `worker_released` flag prevents early
release even when completion has already been recorded. Cleanup ambiguity
classified as `OperationCleanupRequired` retains that hold and stops new worker
claims until startup recovery succeeds. The metadata-error boundary is described
in the restart and ownership section below.

Status responses contain opaque operation and plan IDs, state, parameter
digest, timestamps, attempt count, cancellation/publication flags, bounded error
categories, and a typed verified result. Result fields are manifest and optional
artifact digests, counts, byte totals, and allowlisted coverage categories.
The journal does not store access tokens, arbitrary exception messages,
conversation bodies, or filesystem destinations. Historical plans, reviews,
and jobs do not currently have an automatic deletion policy; operators must
account for their continued metadata retention.

## 4. States and ownership

Prepared plans are separate immutable records. Jobs begin in `queued`.

| State or transition | Meaning |
| --- | --- |
| `queued` → `running` | One exclusive worker claims a fenced attempt |
| `running` → `verifying` | The executor reaches output verification |
| `running` / `verifying` → `cancel_requested` | Cancellation is recorded before a publication decision |
| `cancel_requested` → `cancelled` | The executor has observed cancellation and unwound |
| `queued` → `cancelled` | No executor owns the job; cancellation is immediate |
| `verifying` → `completed` | Authorized output was published and verified with no reported semantic gaps |
| `verifying` → `partial` | Authorized, verified output has explicit semantic coverage gaps |
| Active state → `failed` | A handled failure occurred before publication authorization |
| Active state → `interrupted` | Ownership ended unexpectedly or publication/cleanup is ambiguous |
| `interrupted` → `completed` / `partial` | Restart inspection independently verifies the recorded output |
| Reconciled `interrupted` → `queued` | An explicit, authorized retry reuses the intended output ID |
| `queued` → `expired` | Its plan or review expired before worker admission |

`partial` never means that a process crashed halfway through copying bytes.
Cancellation after the publication decision returns `publication_committed`;
the private publication may finish. Delivery must still pass current access
checks. Bytes already delivered cannot be recalled by a later cancellation.

The worker holds an operating-system lock beside the metadata database for its
entire lifetime. Acquiring that lock allocates a new persisted worker epoch.
Every attempt also has a unique token and increasing attempt number. The live
session, claim thread, database epoch, worker token, attempt number, and attempt
token must agree before checkpoint, authorization, completion, or failure.

There is no time-expiring worker lease. A timed-out shutdown does not close the
lock or release resources while an executor can still publish. `shutdown()`
returns `False` in that situation. Process exit releases the OS lock; the next
owner reconciles the prior epoch before admitting work. Do not fork after
starting a worker, replace the database while it is open, or unlink its lock
file. Multiple hosts and network-filesystem lock semantics are outside this
reference contract.

## 5. Publication and revocation ordering

The publication protocol has distinct boundaries:

1. Admission allocates an immutable intended output ID. The executor prepares
   bytes in an owned workspace and independently verifies them.
2. The executor enters `verifying` and hashes the staged manifest or delivery
   receipt. A delivery receipt binds the ZIP digest and enclosed manifest.
3. `authorize_publication()` opens an immediate SQLite transaction. The trusted
   callback revalidates the principal, current policy/acceptance, exact grant
   version, generation, action, and applicable ancestor grants through that
   **same connection**. The expected manifest digest and publication decision
   are recorded before the transaction commits.
4. The same live worker publishes with the core's atomic no-replacement
   primitive. Its OS lock remains held between authorization and publication.
5. The application verifies the published result, registers the immutable
   output, and records completion. Unfinished registered outputs are withheld
   by the application's origin-operation check.
6. The executor finishes private cleanup before releasing its reservation.

A revocation committed before step 3 prevents the decision. If the decision
commits first, the authorized private publication may finish after revocation;
future disclosure still fails current access checks. Reading a grant in an
unrelated transaction immediately before a rename is not an equivalent fence.
The application uses one supplied transaction while traversing authorization
ancestors to avoid nested-connection lock conflicts and inconsistent decisions.

The active operation remains bound to its exact reviewed primary grant, version,
and acceptance receipt. For an already completed ancestor, a later explicit
human acceptance may renew access to that same ancestor resource, generation,
and action. Each required ancestor must be authorized independently; a new child
or download grant alone is insufficient. Historical creating plans and receipts
remain immutable. Renewal does not authorize an unreviewed change to a queued
or running operation.

A returned permit is usable only by its live owning attempt and intended
output. Repeating authorization with the same manifest digest is idempotent;
another digest fails. Completion requires the recorded digest and typed
verification result. The executor is trusted to perform the actual independent
verification; constructing `VerifiedResult` alone does not verify bytes.

## 6. Restart and temporary-byte ownership

Startup acquires the OS lock, recovers proven operation workspaces and upload
pins, and then reconciles old attempts. Retention cleanup follows publication
reconciliation so an expired delivery artifact cannot disappear before its
previously committed publication is classified.

`application.staging.OperationWorkspaces` records the exact operation/output ID
pair and a random ownership marker. Its directory resides below private service
scratch storage on the output filesystem. Scoped controls route archive stages,
ZIP extraction, package stages, and verification extraction into that directory.
Handled completion removes only this owned workspace. Startup cleanup requires
both its database record and matching marker. Unknown directories are preserved.
Missing, conflicting, or incomplete markers require operator review; the code
never invents replacement ownership evidence to enable deletion.

Filesystem, ownership, and expected persistence failures during workspace
discard are classified as `OperationCleanupRequired`. The classification covers
the initial ownership-ledger read and the final ledger deletion transaction,
including commit failure. When this exception leaves a live worker executor,
the worker retains `worker_released = 0`, stops new claims, and closes its
ownership session after execution unwinds. A previously recorded completed or
partial result remains distinct from unresolved temporary cleanup.

The final ledger transaction follows directory removal. If that transaction
fails, the directory may already be absent while its ledger record remains.
Startup can retire that record without recreating a marker or adopting another
directory. A finalization error can also follow a successful commit, leaving
both directory and ledger absent; startup then proceeds to normal operation
reconciliation after cleanup recovery succeeds. A persistent recovery failure
stops startup before reconciliation can release old holds. Unknown directories
remain untouched.

The worker reservation guarantee applies to worker execution and its startup
reconciliation. Other callers, including download verification, receive the
cleanup exception at their own boundary; the workspace helper itself does not
own a worker reservation. Regression evidence is recorded in
[consent and cleanup verification](../engineering/consent-cleanup-verification.md).

The output inspector runs outside the SQLite transaction while the exclusive
worker lock remains held. It returns `None` only after establishing that the
intended output does not exist. Existing output must independently verify and
match the recorded manifest digest. Corruption, an unexpected digest, or an
inspection failure leaves the job interrupted and ineligible for retry.
Cleanup uncertainty also stops startup admission. A published result is never
overwritten to make a retry appear successful.

Process-interruption tests cover stops before authorization, after authorization,
after publication, and after completion was recorded but before the executor
released its reservation. These tests do not simulate a host power failure or
establish synchronization guarantees for payload files and parent directories.

## 7. Integration obligations and costs

`OperationWorker` receives an executor, output inspector, optional exclusive
startup callback, and optional failure classifier. The executor must freshly
authorize before content I/O; claiming a queued job checks its review lifetime,
not current grant validity. The application throttles ordinary journal/access
checkpoints to at most four per second and forces checks at important phase and
publication boundaries. A single uninterruptible system call or JSON decode
can extend cancellation latency; no wall-clock service target is asserted here.

SQL indexes support owner pages, queued selection, and a partial index over
reserved jobs. Reservation aggregates visit the bounded pending/live set.
Canonicalization uses O(P) bytes for bounded plan size P; recovery selection
sorting uses O(S log S) comparisons for at most 100 identities. Status pages
materialize O(L) bounded rows. Reconciliation and workspace removal cost O(B)
I/O in the bytes inspected or removed. Payload hashing, parsing, and collection
verification retain the bounds documented by their own components.

Component schema version 1 is installed transactionally. Unknown versions fail
closed; automatic migrations are not provided. The rollout and backup procedure
must preserve both metadata and immutable output generations and must never
restore an older grant database as if later revocations had not happened.

See [private service runbook](../operations/private-service-runbook.md),
[private pilot validation](../engineering/private-pilot-validation.md), and
[ChatGPT delivery plan](chatgpt-delivery-plan.md).
