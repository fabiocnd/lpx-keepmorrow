# Import and Collection Contract v1

**Status:** Implemented local milestone; experimental source compatibility
**Reviewed:** 2026-11-12
**Publisher:** Lopix Neural Inc.
**Engineering lead:** Fabio de Sousa Lopes

This contract defines the supported import profile, the evidence retained in a
collection, and the limits of recovery. The implementation has synthetic
behavioral coverage. **No representative real account export has been validated
for this release.** The profile is not an OpenAI export specification, and its
success does not establish account-wide completeness.

## 1. Inputs and publication

The `import` operation accepts explicitly selected local directories or ZIP
files and a stable `--account-namespace` label. It creates a separate destination
that must not already exist. An optional `--previous` argument extends a verified
full collection from the same namespace into another new destination. Source
directories, source ZIPs, and previous generations remain unchanged.

Every user-facing processing command requires the exact current terms and
privacy versions before inspecting selected content. The current declarations
are `--accept-terms 2026-11-12-draft.2` and
`--accept-privacy 2026-11-12-draft.2`. They record a local operation-scoped
declaration, not authenticated identity or legal enforceability. See the
[consent boundary](consent-boundary.md) and [legal draft status](../../legal/README.md).

The application copies and hashes source files into private staging before
semantic interpretation. It derives metadata only from those preserved files.
Before publication it validates the collection and independently rereads the
archive payload against its manifest. ZIP intake exits, including its final
source checks, before publication can complete. Existing destinations are never
overwritten.

Publication uses the archive core's supported atomic no-replace operation. It
establishes an atomic visibility boundary, not `fsync`-based crash durability.
Handled failures and cancellation remove the operation's staging output. A hard
process kill can leave temporary files. Durable jobs, automatic resume, and
abandoned-staging recovery are not implemented.

## 2. Experimental source profile

The adapter identifies filenames matching
`conversations(?:[-_]?\d+)?\.json`. Examples include `conversations.json`,
`conversations1.json`, `conversations-1.json`, and `conversations_001.json`.
Matching is case-sensitive. Files are processed in canonical path order; numeric
suffixes do not establish chronological order.

All candidate conversation files must share one parent directory. A wrapping
directory such as `export/conversations.json` is supported, including deeper
wrappers. Candidates under multiple parent directories produce an explicit
`ambiguous_export_roots` observation and an unsupported semantic result. Other
supplied files are still preserved. A wrapper is a filesystem directory; an
object wrapping the conversation array inside JSON is not supported.

Each recognized document must be UTF-8 JSON containing a top-level array. Before
decoding, byte, nesting, and lexical-token budgets bound work. Duplicate object
keys, invalid Unicode, non-finite values, and exponent overflow are rejected.
A malformed document remains preserved and is reported as `malformed`; a valid
JSON value outside the supported top-level shape is reported as `unsupported`.
Resource exhaustion and source-integrity failures cancel the operation rather
than produce a truncated successful catalog.

### Conversation identity and source records

Each supported conversation record is an object with:

- A nonempty `id` or `conversation_id`. If both are present, they must agree.
- A `mapping` object containing message graph nodes.
- An optional string `title`; absent or unsupported titles produce an observation
  and an empty derived title.
- An optional `current_node` identifier that must exist in the mapping when set.
- An optional `project_id` interpreted only according to the association rules
  below.

Identifiers retain their source spelling. Missing identifiers, contradictory
identifiers, and invalid graph structure reject the affected record explicitly.
Titles are never identity evidence.

The logical conversation key is SHA-256 over compact canonical UTF-8 JSON of
`["openai.chatgpt", account_namespace, source_id]`. Canonical serialization uses
sorted object keys, `ensure_ascii=False`, separators `,` and `:`, no non-finite
numbers, and no trailing newline. The same serialization of the **complete
decoded source record** defines its `revision_id`.

Consequently, renaming a conversation preserves its logical identity but creates
a new revision. Changes to unknown source fields also affect the revision.
Whitespace or object-key ordering changes alone do not create a new canonical
record revision. Original file hashes describe the exact file bytes, including
formatting; they are separate from canonical record hashes.

Unknown fields remain in the preserved original JSON. The normalized catalog
does not claim to interpret every field. Each occurrence records its capture,
source path, array index, and canonical record digest.

### Message graph and readable text

Each mapping node declares `parent`, `children`, and `message`. A node's optional
`id` must agree with its mapping key. Null-message nodes remain structural nodes;
they are not discarded as empty messages. Multiple roots and branches can be
retained when their declared relationships are internally consistent.

Validation checks unique child edges, existing parents and children, reciprocal
relationships, and absence of cycles. Iterative graph reconciliation is
`O(nodes + edges)`; canonical node ordering adds sorting work. The derived view
lists the graph with explicit identifiers instead of pretending that every
branch belongs to one linear transcript.

Recognized text content types are `text`, `multimodal_text`, `code`, and
`execution_output`. The adapter reads supported string parts, explicit text
parts, or a supported content object's string `text`. Multiple text parts are
joined with newlines in the derivative. Unsupported content parts remain in the
original record and generate observations. A readable text field is therefore
an indexable derivative, not a replacement for the source record.

## 3. Files, images, and artifact evidence

All supported regular files in a selected source are preserved as bytes,
regardless of extension. This includes images and binary artifacts; preservation
does not require decoding an image, executing an application, or opening a 3D
model. Empty files and empty directories are retained.

The semantic adapter recognizes attachment objects in
`message.metadata.attachments` and `image_asset_pointer` content objects or parts.
Reference metadata can include an asset pointer, URL, identifier, original name,
and media type. These values are evidence, not download instructions.

**An explicit safe `relative_path` is the only automatic file binding in this
profile.** It is resolved relative to the recognized conversation-file directory
and must match a supplied inventory entry exactly. A matching filename label,
asset identifier, extension, or similar title does not establish a binding.
This profile does not promise that actual OpenAI exports contain `relative_path`;
formats using other associations remain unresolved until supported evidence is
implemented and validated.

| Artifact status | Meaning |
| --- | --- |
| `stored` | An explicit path matches a supplied file; size and SHA-256 are recorded. |
| `not_supplied` | An explicit safe path has no corresponding supplied file. |
| `unresolved` | Reference metadata exists without an explicit inventory binding. |
| `external_reference` | An HTTP(S) reference is retained without a local path binding or network request. |
| `unsupported_reference` | The reference shape or declared path is unsupported. |
| `excluded_by_selection` | A previously stored whole conversation source document was deliberately omitted from a selected package. |

Oversized artifact reference strings, names, or media types remain only in the
original record with an `oversized_artifact_metadata` observation. The respective
derived field ceilings are 8,192, 4,096, and 256 UTF-8 bytes. Original bytes are
not truncated. Supplied files without recognized conversation bindings remain
visible in the capture inventory.

The application never follows source URLs, infers an unavailable original from
a thumbnail, or regenerates missing media. Artifact inclusion also does not
certify that an arbitrary file is safe to execute or complete for its intended
application.

### ZIP transport profile

ZIP intake retains the complete original container and the extracted supported
files. The original container is stored separately at
`captures/<storage_id>/original.zip`; extracted files are stored beneath
`captures/<storage_id>/source/`.

The current profile supports single-disk stored and deflated members, including
streaming data descriptors with and without signatures. It explicitly rejects
ZIP64, multipart archives, encryption, unsupported compression methods,
self-extracting prefixes, extra trailing data, symlinks, special files,
overlapping members, unsafe paths, and inconsistent local/central metadata.

The central directory's byte size and actual entry count are checked before
`zipfile` builds its index. Extraction validates actual decompressed byte counts,
CRC values, and stream completion; declared sizes alone are not trusted. Source
identity and timestamps are checked again when intake closes. Extraction uses a
temporary directory that is removed after normal use or a handled failure.

ZIP intake budgets expanded content and the original ZIP separately. The final
archive's total-byte limit includes **both** copies plus all other preserved and
derived files. A ZIP can therefore pass intake limits yet exceed the final
collection's combined budget.

## 4. Captures, revisions, and associations

Every supplied capture retains its own files and occurrence provenance. The
source fingerprint covers the deterministic source inventory and, when present,
the original ZIP digest. A capture identifier also includes the account namespace
and capture ordinal. Repeating an identical export produces another capture
occurrence with the same source fingerprint; it does not silently erase that
capture event.

Within a collection, identical logical revisions share one normalized revision
record. Different captures can contribute occurrences of that revision. Repeated
or conflicting occurrences within one source capture are retained and reported;
the importer does not choose an undocumented winner.

Association states remain distinct:

- `project_confirmed`: the supported source `project_id` field or an explicit
  operator decision supplies the project identifier and evidence.
- `standalone_confirmed`: an explicit operator decision establishes standalone
  classification. The source adapter does not infer it from absent metadata.
- `association_unknown`: the source lacks usable project evidence, or the
  operator explicitly records an unknown classification.

In particular, null or missing `project_id` does not establish standalone status,
and `gizmo_id` is not interpreted as a project identifier. Source-field evidence
reflects this experimental profile; it is not an independent attestation of
native ChatGPT project membership.

The effective classification uses the most recently supplied capture occurrence,
then explicit operator decisions. Capture order reflects the supplied sequence,
not a verified platform timestamp. `associate` writes a new generation with a
reason and chained decision identifiers. Source associations remain unchanged.
Decision hashes establish internal consistency, not authenticated authorship.

## 5. Collection representation and coverage

The outer container uses the existing directory-archive manifest. Its payload
contains `catalog.json`, `report.json`, `index.html`, and capture contents.
The catalog declares `lpx-keepmorrow.collection`, version `1`, provider
`openai.chatgpt`, and experimental parser compatibility. Its structural schema is
[collection-v1.schema.json](../../schemas/collection-v1.schema.json).

| Layer | Responsibility |
| --- | --- |
| Archive manifest | Exact file inventory, paths, sizes, and byte digests. |
| Capture records | Original-container evidence, supplied files, parser version, source-document outcomes, and observations. |
| Logical conversations and revisions | Namespaced identity, graph nodes, source occurrences, and artifact references. |
| Coverage report | Counts and explicit observations for the supplied material. |
| Passive HTML view | Escaped human-readable browsing with local download links; no source execution or remote requests. |

Source-document status is `parsed`, `malformed`, or `unsupported`. A parsed
document records its known array length and accepted/rejected record counts.
Malformed or unsupported documents have `record_count: null`, with no invented
record count. Summary `source_records` totals the known counts only. A zero total
does not prove that an unknown document, an unrecognized format, or the account
contains no conversations.

Capture status is `complete`, `partial`, or `unsupported`. `complete` means the
supported profile produced no recorded observations for that capture. It does
not establish a complete account export. Unsupported or unavailable content
remains observable through originals and coverage metadata.

Runtime validation supplements JSON Schema with inventory binding, namespaced
identity recomputation, graph topology, source-record indices, artifact byte
bindings, summary reconciliation, decision-chain validation, path portability,
and configured aggregate limits. Schema validation alone cannot establish these
cross-record relationships or file integrity.

## 6. Recovery and selected packages

`restore` recovers the full payload into a separate new directory. `recover`
instead packages selected conversations, a confirmed project, or one selected
revision, together with available bound artifacts.

A selected package declares `scope: "selected_conversations"` and records the
parent manifest digest. It retains normalized selected records and their source
provenance, but excludes complete conversation source documents and original ZIP
containers. Those originals can contain unrelated conversations. If a selected
record references a known conversation source document as an attachment, that
artifact becomes `excluded_by_selection` rather than copying the entire source.

This is a deliberate derivative, not a byte-identical extraction of the complete
original conversation JSON. Full originals remain in the parent collection.
Unrelated association decisions are omitted; retained decisions are chained
again for the selected package.

**Arbitrary selected binary attachments are copied intact, not content-redacted.**
A selected document or nested archive can itself contain additional information.
The selection boundary does not inspect or sanitize every file format and does
not authorize sharing the resulting package with another party.

Portable recovery produces ordinary files. Native recreation of ChatGPT chats,
Projects, sidebar entries, or account settings is not implemented.

## 7. Resource and performance contract

| Boundary | Default ceiling |
| --- | --- |
| Archive entries, including directories | 10,000 |
| Archive total payload / individual file | 10 GiB / 2 GiB |
| Archive manifest / ZIP central metadata | 8 MiB |
| Binary copy or inflate buffer | 1 MiB; configurable up to 16 MiB |
| Source conversation JSON file / per-capture JSON total | 32 MiB / 128 MiB |
| Source records / nodes / edges per capture | 10,000 / 100,000 / 200,000 |
| Source artifact references / observations per capture | 100,000 / 10,000 |
| Collection captures / logical conversations / revisions | 64 / 10,000 / 20,000 |
| Collection occurrences / nodes / artifact references | 40,000 / 200,000 / 100,000 |
| Collection catalog and retained metadata budget | 64 MiB |
| Indexed text per capture or collection | 64 MiB |
| Association decisions | 10,000 |
| JSON structural depth / lexical tokens per decoded document | 64 / 2,000,000 |
| Query characters / returned item count / encoded response | 1,024 / 200 / 1 MiB |

These are explicit runtime defaults, not proven production capacity targets.
Python API limit objects support documented positive-integer overrides. The
source parser's maximum configured nesting depth is additionally capped at 128.
The archive and final catalog must satisfy their own limits even when an input
passes its intake limits.

Aggregate retained metadata is charged before capture, revision, and occurrence
insertion, including artifact metadata. The charge is conservative and includes
delimiter allowance. Final serialized catalog size is checked again. JSON
decoding still materializes one bounded source document at a time; bounded binary
buffers do not imply constant overall memory or a constant RSS limit.

For total bytes `B`, graph nodes `V`, edges `E`, and inventory entries `F`, byte
copying and full verification each require `O(B)` work. Graph validation is
`O(V + E)`; canonical ordering introduces sorting costs. Literal search scans
retained text and does not execute regular expressions or invoke a model.
Collection loading verifies archive bytes before a query, so that entry point
also incurs the full integrity read.

New generations physically copy prior captures. Extending a collection therefore
processes prior plus new payload bytes; it is not an incremental blob store or
physical content deduplication. The composite writer avoids a second payload
copy solely to wrap the completed collection, while retaining an independent
verification read. ZIP extraction adds temporary expanded data and its own
decompression pass. No throughput improvement is claimed without a measured
same-workload comparison.

## 8. Command outcomes

| Exit code | Meaning |
| --- | --- |
| `0` | Requested operation completed; an import-style result has complete semantic status, or a read/verification operation succeeded within its stated scope. |
| `1` | Ordinary archive verification found inventory or byte mismatches. |
| `2` | Acceptance, argument, validation, filesystem, or resource failure; no completed operation is asserted. |
| `3` | A verified collection was published with partial or unsupported semantic coverage. |
| `130` | User cancellation; no completed result is asserted. |

An intentionally selected package currently has partial capture status and
therefore returns `3` when `recover` successfully publishes it. Callers must read
the structured result instead of treating every nonzero code as the absence of
an output. Conversely, `verify --collection` can return `0` for a structurally
valid partial collection; it validates integrity and the contract, not account
completeness. Argument syntax errors use argparse's normal exit behavior.

## Implementation references

- [Source adapter](../../src/keepmorrow/importers/chatgpt.py)
- [ZIP intake](../../src/keepmorrow/importers/zip_intake.py)
- [Collection validation](../../src/keepmorrow/catalog/model.py)
- [Collection operations](../../src/keepmorrow/catalog/service.py)
- [Archive assembly](../../src/keepmorrow/archive/assembly.py)
- [Reference core limitations](reference-core.md)
