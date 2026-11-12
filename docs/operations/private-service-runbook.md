# Private service runbook

**Applies to:** LPX Keepmorrow 0.3.0 reference pilot

**Owner:** Lopix Neural Inc.

**Contact:** fabio@lopixneural.com

**Review date:** 2026-11-12

This runbook covers explicit setup, orderly shutdown, process restart,
retention, and recovery of the private service. It does not record a deployed
service, a connected ChatGPT account, or a completed live identity-provider
exercise. Those gates remain separate in the
[private pilot validation record](../engineering/private-pilot-validation.md).

Project-owned source in this revision uses Apache License 2.0. The historical
development repository stays private; public distribution uses a reviewed source
snapshot with a fresh root commit. Source licensing, actual public publication,
and hosted-service qualification are separate decisions and evidence gates.
The maintained product's free direction does not restrict downstream rights.

## 1. Install and initialize a local operator instance

Use a reviewed checkout and the tested Python environment for the release.
Install the optional service dependencies from the pinned project extra:

```sh
python -m pip install -e '.[chatgpt]'
```

Review the UI build instructions in [the ChatGPT UI package](../../ui/chatgpt/README.md)
when changing its source. The Python service consumes the bundled HTML asset;
editing UI source without rebuilding does not update that bundle.

Choose a new absolute directory whose parent already exists. The following
paths are placeholders for an operator-selected location:

```sh
python -m keepmorrow.application.cli init /absolute/new-service --operator local-owner --port 8765
python -m keepmorrow.application.cli check --configuration /absolute/new-service/service.json
python -m keepmorrow.application.cli serve --configuration /absolute/new-service/service.json
```

The installed `keepmorrow-service` entry point offers the same commands.
Initialization creates private configuration, bundled policy copies, and a
private operator-key file. It does not print the key, inspect source content,
grant consent, register an archive, or enable remote MCP authentication. Enter
the key only in the local portal opened on `http://127.0.0.1:8765`; do not put it
in a URL, repository, screenshot, chat message, or shared command history.

Operator mode is restricted to one local identity. An account namespace inside
an imported export remains source provenance; it is never an ownership claim.
The configured identity and its exact grants determine access.

`check` validates configuration and policy bytes. Its success does not establish
that an identity provider is reachable, a ChatGPT connection works, or a source
collection has been verified.

### Reproduce the synthetic HTTP pilot

The [HTTP smoke runner](../../tests/smoke/run_private_portal.py) exercises a real
loopback socket and the portal's published HTTP endpoints. On Linux, initialize
a separate, new service directory with the exact test identity:

```sh
python -m keepmorrow.application.cli init /absolute/new-synthetic-pilot --operator synthetic-pilot
python tests/smoke/run_private_portal.py --configuration /absolute/new-synthetic-pilot/service.json --launch-service
```

The Linux child launcher starts the service, waits for readiness, runs the
workflow, and shuts down its own process. It also works when an execution
environment isolates each command's network: server and client stay in the same
command. It does not expose a preview URL or leave a hosted service running.

The runner accepts no source-content path. It builds its own synthetic export
with a PNG and opaque binary fixtures. It checks upload authorization, fixed
consent deadlines and refusal of deadline edits, exact review, idempotent start,
queries, selected recovery, download integrity,
ancestor revocation, and logout. Its acceptance and review gestures are test
fixtures, not actual human or legal acceptance. The JSON report excludes keys,
cookies, runtime paths, and operation/resource handles.

Each run requires a fresh instance. The child launcher rejects an initialized
directory containing runtime state before starting maintenance. Never reuse a
personal or customer service for this test. Keep the resulting test state out
of Git; the CI artifact includes only the sanitized JSON report. See the
[recorded evidence](../engineering/private-pilot-validation.md#synthetic-http-pilot).

## 2. Register an existing selected collection

The preferred normal flow receives an explicitly selected upload through the
human portal. An already preserved directory collection can also be registered
through a deliberate local verification command:

```sh
python -m keepmorrow.application.cli register \
  --configuration /absolute/new-service/service.json \
  --collection /absolute/selected-collection \
  --identifier selected_collection \
  --subject local-owner \
  --output /absolute/new-service/service-with-collection.json \
  --accept-terms 2026-11-12-draft.4 \
  --accept-privacy 2026-11-12-draft.3
```

Use the exact policy versions packaged with the release being operated. The
command verifies the supplied collection and writes a **new** configuration
without replacing the selected configuration. Review that file and explicitly
restart with it. Registration does not create the human acceptance required
for connected content access. Never point an operator registration at another
person's archive without the required authority.

## 3. Storage and process ownership

Keep the state directory, output directory, operation scratch directory, SQLite
databases, and worker-lock sidecar on the supported local storage arrangement.
Operation scratch and outputs must share a filesystem for no-replacement
publication. Their roots require private permissions on POSIX; Windows also
requires operator-managed access controls appropriate to the host.

Run one service process for a state directory. A second worker must fail
exclusive admission. Do not run multiple ASGI workers, fork a running worker,
replace the database while the process is live, or remove the lock sidecar to
force access. A lock timeout is not evidence that the other process stopped.

The service maintains separate concepts:

- **Managed outputs:** immutable collection generations and expiring delivery
  packages, recorded in the resource registry.
- **Declared reservations:** queued, interrupted, and live-executor storage
  estimates. Completed status does not release a still-running executor's hold.
- **Upload pool:** separately bounded private intake storage with ownership,
  expiration, and active-borrow pins.
- **Operation workspaces:** exact journal-owned scratch directories with
  matching ownership markers, removed on handled completion or safe restart.

Admission combines managed-output accounting, pending reservations, and the
reserved upload-pool ceiling. It also checks free disk space. These controls
are not filesystem quotas and do not reserve kernel resources. Monitor the
filesystem, metadata growth, external operator-registered archives, and any
unrecognized directories separately.

Configuration requires the following minimum before any operation can be
admitted:

```text
upload_pool_bytes = 4 * max_upload_bytes
max_storage_bytes >= upload_pool_bytes + 2 GiB
```

The 2 GiB term is the declared reservation for one operation. Default 128 MiB
uploads therefore require at least 2.5 GiB of configured managed storage; the
default is 4 GiB. Raising the upload ceiling to 1 GiB requires at least 6 GiB.
Retained outputs and additional queued reservations consume the remaining
budget. A configuration satisfying this minimum still needs actual free space
and does not establish a measured capacity envelope.

## 4. Normal execution and shutdown

A user accepts the displayed policy documents for selected actions and a fixed
resource generation. Upload, operation review, and delivery have separate
scopes. The portal records human review of the canonical plan; a model tool
cannot manufacture that review. A repeated idempotency key returns the same job.
A fresh deliberate capture needs a new key and an unused human review.

Check operation status and cancellation through the control plane. These
requests do not wait for the content-worker slot. A cancellation before the
publication decision is cooperative: the worker acknowledges it at a safe
checkpoint and retains resources while unwinding. After the decision commits,
`publication_committed` means private completion may continue. A new delivery
request still requires current authorization.

For shutdown, stop accepting new external requests and let the application
lifespan request worker cancellation. `PreservationService.stop_worker()` waits
up to five seconds and reports whether the executor stopped. A `False` result
does not authorize another worker to start; the live worker retains its lock.
Allow it to unwind. A forced process termination requires restart reconciliation
and may leave an interrupted job. Do not label that job completed manually.

## 5. Startup and interruption recovery

Normal startup performs the following sequence under exclusive worker ownership:

1. Recover exact ledger-owned operation workspaces and stale upload pins.
2. Fence old attempts using the new worker epoch.
3. Inspect any previously authorized publication outside the SQL transaction.
4. Verify its bytes and the recorded manifest/receipt digest before completion.
5. Begin normal admission and run retention maintenance.

An existing output is never replaced by restart. Output absence leaves an
interrupted job eligible for an explicit retry, subject to current access,
review lifetime, and the attempt ceiling. Corrupt or unexpected output remains
interrupted and ineligible for retry. Preserve the evidence and investigate the
fixed error category; do not edit journal rows to force success.

Workspace cleanup requires both the journal record and its exact ownership
marker. An unknown directory, missing marker, or conflicting marker is not a
cleanup target. Investigate it offline, establish ownership from retained
evidence, and use an explicit operator recovery procedure. Do not recreate a
marker merely to make a directory deletable. Global temporary directories are
never swept by prefix.

`workspace_cleanup_required` or `journal_unavailable` on the worker requires
operator attention. A classified workspace cleanup failure retains the worker's
reservation and stops new claims, including a failure to read or retire its
ownership ledger. If directory removal succeeded before the ledger transaction
failed, the ledger can remain while the directory is already absent. Preserve
that state for normal startup recovery; do not recreate a marker or manually
clear the reservation. Persistent cleanup errors block startup before old
operation holds are reconciled.
After addressing the underlying problem, restart through the normal ownership
and reconciliation path. A verified published output can remain completed while
temporary cleanup is unresolved; publication and cleanup are separate facts.

## 6. Retention and revocation

The default upload lifetime is at most one hour, further capped by configured
retention. The default delivery-package lifetime is 24 hours; the configured
pilot range is 60 seconds through seven days. Package expiration is measured
from operation creation, so a delayed job can have less delivery time remaining.
The human portal displays the configured limits.

Before acceptance, the portal also displays the authorization deadline in UTC.
It is fixed when the scope is prepared and is not extended by delayed
submission. Sign-in and confirmation can expire sooner. After updating the
service, reload the portal and prepare a fresh scope; older forms that lack the
required deadline are refused. Existing accepted grants retain their recorded
expiration.

Maintenance runs on startup after reconciliation and periodically while the
service is running. Active upload pins prevent cleanup of borrowed bytes.
Package removal targets only expired service-owned delivery directories whose
manifest matches the registry. It is gated by the content-I/O slot. Persistent
collection generations and configured source archives are not included in this
sweep. `shutil.rmtree` is ordinary filesystem removal, not secure erasure.

Revocation blocks new admission, publication decisions that have not committed,
and subsequent disclosure under the revoked scope. Derived-resource access
also rechecks the configured authorization lineage. Previously delivered bytes
cannot be recalled. Retained output and operation metadata follow their stated
retention rules; revocation does not silently delete original source archives.

An explicitly renewed human grant can authorize a completed ancestor again for
its exact resource, generation, and action. Renew every required ancestor;
granting access only to a derived package does not renew its source lineage.
Queued and running operations still require the exact primary grant/version
and receipt shown in their reviewed plans. Historical receipts are never edited
to make a renewal appear to have occurred earlier.

Historical plans, acceptance receipts, reviews, and job metadata currently have
no automated purge. Declare and implement the operator's required metadata and
backup retention policy before accepting real customer data.

## 7. Backup, rollback, and host-level limits

Before taking an offline recovery snapshot, stop admission and establish that
the executor has finished. Back up metadata databases, relevant SQLite companion
files when applicable, immutable outputs, configuration, and exact policy bytes
as one consistent set. Protect the operator key separately according to its
credential role. A file-by-file copy of an actively changing database and
outputs is not a tested recovery protocol.

Restore into an isolated private directory, preserve the original backup, and
start with disclosure disabled until generations and metadata agree. Reconcile
later revocations from an authoritative current record before allowing access.
An old snapshot must never resurrect permissions that were subsequently revoked.

The component schemas reject unsupported versions and do not implement automatic
migration. Retain the prior executable/environment and its compatible snapshot
for rollback. Do not run an older binary against changed metadata speculatively.
No backup/rollback exercise on a selected deployment host has been recorded yet.

SQLite publication decisions and atomic filesystem visibility do not establish
payload power-loss durability. Validate file synchronization, directory ordering,
storage behavior, recovery point, and recovery time on the actual host before
making a stronger durability commitment.

## 8. Remote ChatGPT pilot

OAuth mode requires an explicitly selected issuer, JWKS endpoint, registered
browser client, allowed principals, resource audience, and authenticated HTTPS
transport. The service socket remains bound to loopback; a selected reverse
proxy or supported private transport supplies the external HTTPS boundary.
An operator key is never a remote MCP bearer token.

Validate live OAuth/PKCE, origin/session handling, current token rejection,
revocation, actual ChatGPT resource rendering, upload selection, and binary
delivery with synthetic data first. Only then run an authorized representative
export. Source-account enumeration, source deletion, native ChatGPT restoration,
public directory submission, and production capacity claims remain outside this
runbook's completed evidence.
