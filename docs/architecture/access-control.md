# Connected Access and Human Acceptance

**Owner:** Lopix Neural Inc.
**Engineering lead:** Fabio de Sousa Lopes
**Status:** Implemented internal metadata boundary; deployment qualification remains separate
**Review date:** 2026-11-12

## Contract and trust boundary

`keepmorrow.access` authorizes an exact principal, resource, immutable generation,
and action using persistent grants and independently recorded human acceptance.
It does not inspect selected collection content. The private application invokes
this boundary before content access, resource admission, and artifact delivery;
other callers must preserve that ordering. The
[consent boundary](consent-boundary.md) distinguishes this service contract from
the local CLI and legacy synthetic development adapter.

`Principal(issuer, subject)` preserves the exact verified identity pair. Its
stable principal ID is a domain-separated SHA-256 digest of the pair's canonical
JSON encoding. Source account namespaces, email addresses, titles, and opaque
resource IDs establish no identity or authority. The store persists the derived
principal ID rather than the raw issuer or subject.

Constructing a Principal does not authenticate a request. These Python APIs are
internal and are not an authenticated service interface. The transport boundary
must validate credentials, including issuer, audience, token validity, and
required scopes, before constructing the principal. It must derive that
principal from verified credentials for every request, never from tool arguments.

## Separate permission and acceptance

`create_grant` records an administrative permission for one resource and
generation, explicit action set, purpose, recipient, and expiry. It does not
authorize content processing until `accept_grant` has recorded a separate human
decision. Grant scopes are immutable. A changed resource, generation, recipient,
purpose, or allowed action set requires another grant. At most 256 unrevoked,
unexpired grants may exist per principal by default. Admission counts and inserts
share the write transaction, so concurrent requests cannot exceed that bound.
Revoked and expired evidence is retained rather than deleted to make room.

`accept_grant` is available only to trusted server code after an authenticated
human interaction. That interaction must display the exact scope, purpose,
recipient, current terms, and privacy notice; validate its session and CSRF
challenge; and verify a deliberate submission. No MCP tool may expose this
method. A Boolean or current policy strings supplied by a model are not assent.

The acceptance record binds the grant ID and version, selected action subset,
current terms and privacy versions and SHA-256 digests, single-use interaction
ID, timestamp, and expiry. Scope metadata is available through the immutable
grant reference. Interaction IDs must be server-issued opaque values. Their
uniqueness prevents replay in the store; the ID alone does not prove a person
acted. Accepting cannot broaden actions, exceed grant expiry, or revive a revoked
grant. The application owns eligibility declarations and must make them part of
its displayed scope and trusted interaction record before content processing.

`PolicySet` is injected. All workers sharing a database must use the same current
policy versions and document digests. Any changed version or digest invalidates
the old receipt for future access. A new deliberate acceptance can authorize the
updated policy. Retained receipts remain historical evidence; old application
or backup restoration must not silently make obsolete policies current again.

The local CLI acceptance contract is separate and remains unchanged.

## Authorization and listing APIs

| API | Result and enforcement |
| --- | --- |
| `create_grant` | Administrative `Grant`; no implicit acceptance |
| `get_grant` | Owner's metadata for consent presentation; no content authority |
| `accept_grant` | Separate `HumanAcceptance` after the trusted interaction |
| `require_access` | `AccessDecision` for an exact current scope |
| `authorize_publication` | Same decision, requiring the caller's immediate transaction |
| `list_grants` | Only the principal's live, current-policy accepted action subsets |
| `revoke_grant` | Atomic revocation of the grant and all linked receipts, with a version increment |
| `revoke_acceptance` | Withdrawal of one receipt; separately accepted scopes remain distinct |

Action names have exact-match semantics. For example, `read` does not imply
`recover` or `download`. The application requires the workspace's `upload` action
before receiving bytes; that permission does not imply `import` or `unpack`.
There is no implicit role or action hierarchy.

`require_access` can bind an explicit grant ID, expected grant version, and
expected acceptance ID. The last field lets an operation require the exact
receipt that was used when its plan was reviewed. The returned decision is an
observation, not a bearer token or durable journal entry.

Unknown, foreign, unaccepted, stale, revoked, and expired scope requests all
raise `AccessDenied` with the same content-free error message. No error includes
resource existence details, source paths, or private content. Invalid input
raises `AccessError`. SQLite failures become `PersistenceError` with a bounded
message; transport boundaries must expose that safe message or category rather
than a traceback or exception cause.

Listing is principal-filtered before pagination. It returns no content and does
not authorize a later read. At most 100 grants and 32 actions per grant enter
application memory. Indexes cover principal/resource/generation and receipt
lookup. Query cost also depends on retained historical receipts; no throughput
or indefinite-history performance guarantee is claimed.

## Publication ordering against revocation

Use the same `SQLiteDatabase` for grants and the operation journal. An operation
must call `authorize_publication` and persist its publication decision inside
one `database.transaction(immediate=True)` block. The returned connection must
be passed explicitly. Opening another connection for the access check would
lose the required ordering.

The implemented `OperationStore.authorize_publication` owns that transaction and
passes its connection and immutable plan to the application's authorization
callback. `PreservationService._authorize` verifies the primary scope recorded in
`plan.scope`, required completed ancestry, and any independent intake scope on
that connection. The journal then persists the publication decision before
commit. Filesystem publication follows the commit while the exclusive worker
still owns the attempt. See the [operation journal](operation-journal.md) for
attempt ownership and recovery.

If revocation commits first, publication authorization fails. If the journal's
authorization decision commits first, private publication may finish. A revoked
grant cannot authorize new admission or disclosure. Every subsequent artifact
delivery requires a fresh authorization check, including any independently
accepted current scope described below. Already transmitted bytes cannot
be recalled. This component does not revoke third-party copies or an independently
issued bearer URL, cancel a running file operation, or define output retention.

The grant version advances once on its first revocation. Revocation without an
expected version is idempotent. An old expected version is refused. Receipts
cannot restore the old grant; renewed permission requires a new grant.

### Renewing disclosure of completed results

The application distinguishes an active operation's reviewed authority from
later access to a completed result. Queued and running operations remain bound
to their exact primary grant ID, version, and acceptance receipt at admission,
checkpoints, and publication. Fresh consent cannot silently rebind those plans;
the owner must prepare and review new work when its original authority ends.

Completed and partially completed results retain immutable historical plans.
Future disclosure requires current human-accepted permission for each ancestor's
exact resource, generation, and action, as well as the requested result's own
access scope. An owner can renew an expired or withdrawn ancestor through a
new explicit grant and acceptance for that ancestor. A new grant on a child
alone cannot restore access when an ancestor remains unauthorized.

This permits long-lived preserved collections to become accessible again after
a resource grant expires, without editing historical receipts or source
bytes. Completed-operation status applies the same current ancestry rules before
disclosing output identifiers and results. A retained or previously completed
artifact is not itself proof of current disclosure authority.

## Metadata database

`SQLiteDatabase(path)` requires an existing ordinary parent directory and a
local filesystem controlled by the service operator. On POSIX, new database
files use mode 0600 and existing files must already have owner-only permissions.
Symbolic links, multiply linked database files, and unsupported companion-file
types are refused. The operator must secure directory ownership and Windows
ACLs; these checks are not isolation from a hostile filesystem owner. SQLite
metadata is not encrypted by this component.

Each transaction gets a separate connection with row access by name, foreign
keys enabled, `synchronous=FULL`, a bounded busy timeout, and trusted schema
evaluation disabled. The default `BEGIN IMMEDIATE` obtains the write reservation
before the authorization clock is sampled. Read-only observations may use
`immediate=False`. Long content I/O must remain outside these transactions.

Borrowed connections must originate from an active transaction of this
abstraction for the same absolute database path. An independently opened raw
SQLite connection or a deferred transaction cannot authorize publication. The
caller must not commit, roll back, or retain a borrowed connection itself.

An application ID prevents adoption of unrelated databases. Component versions
are stored independently in `km_schema_versions`; no component reuses the global
`user_version` field. Initialization is transactional. Existing version mismatches
fail closed without running migration statements. No automatic upgrade or
downgrade is implemented; future migrations require an explicit recoverable
backup and recovery procedure.

The access component stores grant, receipt, interaction, scope, and policy
metadata. Its records contain no bearer credentials, source text, original
filenames, or filesystem paths. Other components in the shared database have
their own bounded control schemas, including necessary source labels and
association reasons; the access component's inventory is not a description of
the entire service database. The private application stops new admission at its
documented 64 MiB metadata threshold. That threshold is not a physical database
quota or an automatic historical-record purge.

SQLite commit durability does not establish payload durability across a host
failure. Backups must preserve revocation and policy state; service restore and
release qualification remain operator tasks.

## Verification scope

Synthetic tests challenge cross-principal isolation, exact action and generation
scope, policy version and digest changes, interaction replay, receipt and grant
expiry, revocation, filtered pagination, and transaction rollback. Integration
tests use competing connections to prove both possible orderings of revocation
and publication authorization, plus expiry after waiting for the write lock.
Application tests also require explicit parent renewal for completed results and
refuse replacement authority for an existing active plan.

Those tests establish the internal metadata contract. They do not demonstrate a
real identity-provider connection, actual human-interface behavior, ChatGPT
account capability, legal enforceability, production capacity, or payload
survival after a host or storage failure.
