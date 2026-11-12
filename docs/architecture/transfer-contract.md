# Bounded Transfers and Recovery Packages

**Owner:** Lopix Neural Inc.
**Engineering lead:** Fabio de Sousa Lopes
**Contact:** fabio@lopixneural.com
**Contract version:** 1
**Implementation date:** 2026-11-12

The transfer boundary accepts an explicitly authorized binary stream and returns
an opaque receipt. The recovery boundary packages a verified collection into a
portable ZIP, then verifies it independently before publication. Neither boundary
enumerates a ChatGPT account, fetches arbitrary URLs, executes imported material,
or asserts native restoration into ChatGPT.

## Authority and ownership

`UploadStore` receives an authenticated, stable `owner_id` from the application.
The application must validate intake consent before calling `receive`; an owner
string supplied by a model or browser is not an authentication credential. The
store enforces ownership of handles, while the application enforces active
consent, collection grants, and delivery authorization.

The root must be a new or empty, dedicated service directory. An existing store
must carry the supported ownership/version marker. Storage paths use random,
server-generated `u_` handles followed by 128 random bits. Display names and media
types are bounded metadata and never participate in filesystem path selection.
No receipt or package result contains a storage path.

The implementation assumes service-owned directories with stable ancestors.
It rejects observed symlinks and non-regular files. It does not claim isolation
from a privileged local attacker who can replace directories, modify SQLite
metadata, or overwrite both bytes and their expected hashes.

## Upload lifecycle

| API | Contract |
| --- | --- |
| `receive(owner_id, source, display_name=..., ...)` | Reserve count and byte quotas; stream, hash, and count bytes; commit a ready receipt only after exact-length checks |
| `resolve(owner_id, upload_id)` | Return unexpired owned metadata; unknown, foreign, unfinished, and expired handles share an unavailable error category |
| `open_upload(owner_id, upload_id)` | Pin the object, verify its SHA-256 and length, rewind, and yield `(UploadRecord, BinaryIO)` |
| `borrow_path(owner_id, upload_id)` | Hold the same verified pin while a trusted local worker uses the internal path |
| `discard(owner_id, upload_id)` | Remove one available owned object; refuse while a consumer is using it |
| `cleanup_expired()` | Remove expired ready objects and retry pending deletion; skip receiving and pinned objects |
| `recover_interrupted()` | At exclusive startup, clear abandoned pins and remove interrupted receiving objects before normal admission |

SQLite transactions reserve capacity before payload writes. A declared length
reserves that exact number of bytes; an unknown length reserves the configured
maximum. The stream must end at the declared length. Successful intake replaces
the reservation with the actual count. Receiving, ready, pinned, and pending
deletion objects continue to consume capacity until their owned bytes are removed.
Concurrent admission therefore cannot spend the same quota twice.

The reusable store and the private service have different configured ceilings:

| Admission boundary | Store default | Private-service default |
| --- | --- | --- |
| One upload | 1 GiB | 128 MiB |
| One owner's staged bytes | 2 GiB | 256 MiB |
| All staged bytes | 4 GiB | 512 MiB |
| Upload count per owner / overall | 8 / 64 | 8 / 64 |
| Upload lifetime | One hour | One hour, or a shorter configured artifact-retention period |

Lifetime begins at admission and includes upload time. A slow upload that reaches
expiry fails. The store's chunk size defaults to 1 MiB and cannot exceed 16 MiB;
the HTTP adapter supplies bounded 64 KiB frames. Configured service limits,
provider limits, and deployment limits can impose lower ceilings. None of these
defaults is evidence of actual ChatGPT file-transfer capacity.

Expiry prevents a new consumer from opening an object. An existing consumer
retains its pin until its context exits; cleanup cannot remove its input early.
The delivery adapter separately enforces authority at its output boundary. The
implemented portal rechecks the current browser session, exact download grant,
package availability and expiry, and originating-operation authority before and
after every 64 KiB disk read. A failed check ends further delivery; an incomplete
response cannot satisfy the declared `Content-Length`. Bytes already transmitted
cannot be recalled. A direct caller of the lower-level stream API must supply
its own equivalent delivery boundary. See the
[trusted portal contract](trusted-portal.md#bounded-upload-and-delivery).

Ordinary exceptions and cooperative cancellation remove only the current owned
attempt. A hard process stop can leave a receiving reservation or pin. Startup
reconciliation is explicitly exclusive: calling it while another process or
worker uses the same store is unsupported. Completed uploads survive restart and
are checked before their next content access.

Cleanup inspects only handles present in the durable ledger and deletes at most
the corresponding payload, ownership marker, and empty directory. Unexpected
files, links, or invalid markers cause refusal. Unregistered directories and
source files remain untouched. Deletion releases live storage; it is not a
promise of secure erasure from SQLite free pages, filesystem snapshots, or
operator backups.

## Recovery container version 1

The package is a single-disk, non-ZIP64 ZIP with the directory archive's exact
`manifest.json` bytes and its `payload/` tree at the ZIP root. No envelope document
is inserted into the preserved archive. The existing manifest remains the
authoritative payload inventory; the outer SHA-256 is returned separately.

Packaging preserves the collection it receives. A full imported collection keeps
the supplied ZIP and source files as original evidence. A selected recovery is a
declared derivative: it retains normalized selected records and source provenance
while excluding complete conversation documents and original ZIPs that could
contain unrelated conversations. Available selected binary attachments are copied
byte for byte, including images and otherwise opaque formats; they are not
content-redacted. An attachment can itself contain additional information.
Packaging does not recover unavailable bytes or turn selected records back into
the complete original JSON. See the
[selection contract](import-contract.md#6-recovery-and-selected-packages).

| Budget | Default | Interpretation |
| --- | --- | --- |
| Encoded package | 1 GiB | All ZIP bytes, including headers and central metadata |
| Expanded package | 1 GiB | `manifest.json` plus every payload file |
| Wrapper entries | 10,002 | Payload entries plus `manifest.json` and `payload/` |
| Central metadata | 8 MiB | ZIP central-directory records, names, and supported metadata |
| Payload inventory | Existing archive limits | Independently enforced after extraction |

The wrapper and payload entry budgets are distinct. A payload containing the
maximum permitted 10,000 entries does not lose two entries to its outer wrapper.
Lower configured limits apply. Version 1 refuses an encoded or expanded ceiling
above 1 GiB and refuses a wrapper entry limit at the ZIP64 sentinel. These are
conservative pilot limits, not observed ChatGPT transfer capabilities.

Packing uses stored ZIP members, sorted paths, fixed January 1, 1980 timestamps,
fixed ordinary file/directory attributes, and no comments or extra fields. The
same source bytes and supported manifest representation produce the same ZIP
bytes. This preserves source file contents and directory topology, not original
filesystem timestamps, ACLs, executable attributes, or owner identifiers.

Packing prefixes payload names with `payload/`. The resulting wrapper paths must
still satisfy the archive's portable name, length, and depth rules. A source at
the exact maximum path length or depth can therefore be unsupported by this
wrapper and fails explicitly instead of being renamed.

## Verification and publication

`pack_collection(source, destination, ...)` first validates the complete source
archive and collection catalog. It copies each file into a bounded temporary
ZIP while comparing the actual bytes with its manifest record. It then runs the
guarded ZIP intake against the staged output, validates the extracted archive
and catalog, confirms unchanged manifest bytes, hashes the encoded output, and
rechecks the source inventory. Only then does it publish the new file.

`unpack_collection(package, destination, ...)` hashes the bounded input and uses
the existing ZIP preflight/extraction path. That path rejects traversal, name
collisions, symlinks, special files, unsupported compression/encryption, ZIP64,
multipart layouts, truncated data, incorrect CRCs, and inflated-size overflow.
The extracted root must contain exactly the supported directory archive. Both
archive hashes and collection semantics must validate. A copy into a new staging
directory receives another complete verification before publication.

Both APIs accept a cooperative `checkpoint` callback. Raising from it cancels
the attempt and removes its owned temporary directories. They also accept a
`before_publish` callback after verification and immediately before publication;
the application uses this point for durable attempt ownership and the consent
revocation/publication ordering defined in the operation contract.

Publication uses the archive's no-replacement primitive on supported Linux and
Windows filesystems. An existing or competing destination survives unchanged.
The staged ZIP is created exclusively with private POSIX file permissions. By
default, temporary objects use the destination's parent. A private-service
execution scope places them under the operation's marker-owned scratch directory,
including independent ZIP extraction and verification copies. The service keeps
scratch and publication directories beneath its state root; publication still
requires them to share a filesystem. A cross-filesystem publication is not
silently converted into an overwrite-prone copy.

Normal completion and exceptions remove the current temporary objects. Exclusive
service startup can reconcile interrupted marker-owned workspaces, while
standalone primitives do not provide their own persistent operation journal.
These guarantees cover process-level visibility and cleanup, not payload survival
after power loss; this implementation does not claim a filesystem `fsync`
durability protocol. See the [operation journal](operation-journal.md).

`PackageResult` reports encoded bytes and SHA-256, expanded bytes, payload file
and directory counts, unchanged manifest SHA-256, and the collection's existing
scope. Its verification stage is local package and collection validation. A
successful result does not establish transmission, remote verification, complete
account coverage, or recovery of unavailable source bytes.

The private service stores a delivery receipt beside `package.zip`, outside the
unchanged ZIP contents. That delivery resource's generation is the receipt's
SHA-256; the receipt separately identifies the ZIP digest and enclosed collection
manifest. The upload/unpack path reproduces the enclosed collection generation.
Delivery packages expire according to configured retention measured from the
creating operation's timestamp. Expiry blocks delivery even before a maintenance
sweep removes the wrapper. Cleanup targets only registered owned delivery
wrappers and upload staging; it does not delete the original or recovered
collection generations.

## Resource accounting

For encoded size `Z`, expanded size `B`, file/path count `F`, and chunk size `C`,
payload processing uses bounded `O(C)` buffers; inventory, ZIP records, and
catalog validation retain separately bounded metadata. Path sorting costs
`O(F log F)`. Byte work is linear in the bounded input/output sizes, with multiple
passes retained for distinct integrity stages.

Packing keeps the staged encoded file and one expanded verification copy at the
same time, up to `Z + B` additional disk bytes. Unpacking keeps an expanded
extraction and a separate staged archive, up to `2B` additional disk bytes beyond
the supplied ZIP. The application must reserve this temporary capacity in its
operation scheduler; upload quota alone does not reserve recovery workspace.

The [private service benchmark](../../benchmarks/PRIVATE_SERVICE_BENCHMARK.md)
measures a bounded synthetic application workflow and records exact source
identity, child-process RSS, and sampled scratch bytes. Its observations are
separate from functional correctness and do not establish load capacity or
actual-host transfer limits. Deployment measurements and an authenticated
ChatGPT/portal round trip remain separate release evidence.

## Executable verification

The focused suite uses only synthetic source material:

```sh
PYTHONPATH=src python -m unittest tests.unit.test_transfers_staging tests.integration.test_transfers_packages -v
```

It checks deterministic binary round trips, preservation of noncanonical valid
manifest bytes, quota races, ownership, expiry, active pins, interrupted-process
cleanup, corruption, encoded/expanded/metadata limits, wrapper counts, hostile
paths, cancellation, source mutation, and no-clobber publication.
