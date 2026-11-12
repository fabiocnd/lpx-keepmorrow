# Reference Preservation Core

This document describes the byte-preservation component. Version 0.2.0 composes
it with separate importers and collection services; see the
[collection workflow](collection-workflow.md) and
[import contract](import-contract.md) for those implemented capabilities.

## Status and Scope

This reference implementation provides a narrow, executable slice of the preservation design: create a portable directory archive from an explicitly supplied local directory, verify its bytes and inventory, and restore it into a new destination. The runtime uses Python 3.11 or newer and the standard library. Selecting Python for this reference slice does not finalize the production stack.

The supplied directory is the complete declared input scope. Every supported file, including hidden files, and every directory, including empty directories, is preserved. The core does not read the user's ChatGPT account, parse actual provider exports, infer project associations, resolve conversation identities, summarize content, or fetch referenced assets. A file hash identifies captured content for integrity comparison; it does not identify a logical conversation.

The intended product entry point is `python -m keepmorrow`. It requires explicit acceptance of the current terms and privacy versions before calling archive services. Python service functions are internal building blocks, not a separate supported user interface; another application embedding them must implement its own agreement boundary before user data processing. See [Consent Boundary](consent-boundary.md).

## Module Boundaries

| Module | Responsibility |
| --- | --- |
| `src/keepmorrow/cli.py` | Parse the selected operation, enforce the agreement boundary, and return structured status |
| `src/keepmorrow/consent.py` | Validate explicit, versioned acceptance for the selected operation |
| `src/keepmorrow/archive/model.py` | Define the manifest, limits, reports, portable paths, and strict schema validation |
| `src/keepmorrow/archive/filesystem.py` | Inventory stable source trees, stream bytes, detect observed mutations, and publish without replacement |
| `src/keepmorrow/archive/service.py` | Coordinate staging, local verification, creation, and recovery |
| `src/keepmorrow/archive/assembly.py` | Assemble preserved and generated entries under one bounded, verified publication transaction |

The archive feature owns its contracts and filesystem behavior together. The command-line boundary remains thin. No generic utilities layer, storage provider, model provider, or unused service framework is included.

## Running the Synthetic Example

From the repository root on the validated Linux environment:

```bash
keepmorrow_demo="$(mktemp -d)"

PYTHONPATH=src python -m keepmorrow create \
  examples/synthetic-input "$keepmorrow_demo/archive" \
  --accept-terms 2026-11-12-draft.2 \
  --accept-privacy 2026-11-12-draft.2

PYTHONPATH=src python -m keepmorrow verify \
  "$keepmorrow_demo/archive" \
  --accept-terms 2026-11-12-draft.2 \
  --accept-privacy 2026-11-12-draft.2

PYTHONPATH=src python -m keepmorrow restore \
  "$keepmorrow_demo/archive" "$keepmorrow_demo/restored" \
  --accept-terms 2026-11-12-draft.2 \
  --accept-privacy 2026-11-12-draft.2
```

Read the referenced legal documents before supplying acceptance. Their current status is a development draft; including explicit acceptance does not represent legal approval of that draft or a public launch. The command does not remember agreement across operations. Existing destinations are rejected. The destination parent must already exist and must be outside the source directory.

These commands do not require a package installation. `pyproject.toml` also provides an installable package and console entry point. `setuptools==84.2.1` is the selected build-only dependency; the preservation and collection core has no third-party runtime dependencies. The separate ChatGPT development adapter has an optional SDK dependency. Build isolation may download the pinned backend when it is not already available.

| Exit status | Meaning |
| --- | --- |
| `0` | The requested local operation completed and its reported checks passed |
| `1` | `verify` found inventory or integrity differences |
| `2` | Agreement, input, schema, resource, filesystem, or operation validation failed |

JSON output reports counts, status, the operation's verification stage, and agreement metadata. It does not print preserved file contents. A local verification result never implies a remote transfer or remote integrity check.

## Directory Archive Contract

The archive root has exactly two expected entries: `manifest.json` and the `payload/` directory. Files beneath `payload/` retain their supplied relative paths. `manifest.json` contains:

| Field | Contract |
| --- | --- |
| `format` | `lpx-keepmorrow.directory` |
| `version` | Integer `1` |
| `scope` | `explicitly_supplied_directory` |
| `hash_algorithm` | `sha256` |
| `directories` | All relative directory paths, sorted lexicographically |
| `files` | Sorted records containing `path`, `size_bytes`, and lowercase `sha256` |

The manifest excludes absolute paths, usernames, timestamps, and source content descriptions. Identical paths and bytes produce identical manifest bytes. This is deterministic snapshot metadata, not an ingestion journal or cross-snapshot deduplication engine.

[directory-archive-v1.schema.json](../../schemas/directory-archive-v1.schema.json) defines the JSON structure. Runtime validation additionally enforces canonical order, duplicate-key rejection, parent topology, Unicode normalization, case-fold collision rules, platform-portable names, and configured resource limits. JSON Schema alone does not establish those cross-record invariants. Future formats must receive a new version instead of being silently accepted by this parser.

Relative paths use `/`. Every path must be NFC-normalized Unicode, at most 4,096 UTF-8 bytes, and at most 64 components. Components are limited to 240 UTF-8 bytes. Absolute paths, traversal, empty components, backslashes, device names, unsupported punctuation, Unicode control/format/surrogate characters, and trailing spaces or periods are rejected. Case-fold collisions are rejected across files and directories. Unsupported names are reported, never rewritten.

## Write and Verification Semantics

Creation inventories a stable source directory, copies files into a private staging directory while hashing bounded blocks, rechecks observed source metadata, writes the canonical manifest, and reads the staged payload again to verify the result. Only then is the completed staging tree published to the requested new destination.

Recovery validates the manifest and archive inventory first. It then copies into a separate staging tree, compares the copied records with the validated manifest, and reads the recovered bytes again before publication. Source and archive files remain unchanged. Extra archive-root entries, extra payload entries, missing entries, and differing file bytes prevent a successful recovery.

Verification reports expected file count and expected total bytes. Missing, changed, unexpected, and unreadable-or-changing files are explicit report categories. Malformed manifests, unsupported paths, symbolic links, unsupported file types, and resource-limit violations fail the operation. Ordinary directories and regular files are the only supported filesystem entries. Hard-linked source files are copied as independent files; hard-link relationships are not preserved.

Publication uses Linux `renameat2` with `RENAME_NOREPLACE`, or Windows' no-replacement rename behavior. Unsupported runtime or filesystem primitives fail explicitly. An existing destination, including an empty directory created by a competing process, is never intentionally replaced. Local development validation runs on Linux; the [foundation verification record](../engineering/foundation-verification.md) records inspected Linux and Windows CI outcomes. Other operating systems do not currently support create/restore publication; no execution claim is made for them.

Windows inventory records regular-file metadata through a guarded descriptor so
that inventory and read-time checks use the same timestamp semantics. The
no-follow path observation is bound to that descriptor before its full signature
is accepted. Filename-derived execute bits are masked only for the cross-API mode
comparison; the complete descriptor signature remains authoritative afterward.
This adds one metadata-only open/stat/close cycle per file per scan on Windows,
with one additional handle at a time. Linux retains its path-stat inventory.

The implementation rejects observed symlinks, including symlink ancestors, and detects ordinary source changes through descriptor and inventory checks. It is designed for stable, user-controlled source and destination trees. It does not provide a filesystem-wide snapshot, defend against a hostile process replacing ancestor directories between operations, or support concurrent mutation of the same tree. Atomic publication is a visibility boundary; no `fsync`-based crash-durability guarantee is implemented.

Handled failures remove the operation's own temporary staging tree. A hard process kill or system crash may leave a `.keepmorrow-*` directory. Automatic restart, abandoned-staging discovery, durable job checkpoints, and cancellation/resume are not implemented. No existing destination is deleted as part of cleanup.

SHA-256 comparisons establish consistency with the manifest that was supplied. They do not authenticate an archive publisher or detect an attacker replacing both the payload and its manifest. Digital signatures, an independently trusted manifest digest, encryption at rest, and remote integrity verification remain separate work.

## Resource and Complexity Model

| Default limit | Value |
| --- | --- |
| Payload entries, files plus directories | 10,000 |
| Total payload bytes | 10 GiB |
| Single file | 2 GiB |
| Manifest bytes | 8 MiB |
| Stream block | 1 MiB |

The internal `Limits` contract permits positive integer overrides. Stream blocks may not exceed 16 MiB. Archive-root extras are enumerated under a separate bounded allowance before sorting. Every limit is validated again when reading an archive; manifest declarations are not trusted as allocation instructions.

For total source bytes `B`, entry count `n`, total path bytes `P`, manifest bytes `M`, and block size `C`, payload I/O is `O(B)` per pass. Creation performs a copy/hash pass and a verification read; recovery performs validation, copy/hash, and recovered-byte verification. Sorting is `O(n log n)` comparisons. Metadata, paths, parsed JSON, and lookup tables consume `O(n + P + M)` memory; payload buffers consume `O(C)`. Total process memory is therefore not constant and is not represented by a claim of constant RSS.

No throughput target is asserted by this code. The [benchmark](../../benchmarks/README.md) reports reproducible local experiments with its workload and measurement limitations.

## Validation

Run the focused behavior suite:

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

Coverage includes byte-identical recovery, empty directories/files, deterministic manifests, same-size corruption, missing/unexpected entries, safe cancellation on corruption, existing-destination protection, publication collisions, symbolic links, non-regular files, portable path attacks, malformed JSON, duplicate records, resource ceilings, staging cleanup, CLI status, and acceptance enforcement. Test results must be recorded from an actual run; this document does not imply that every operating system was tested.

The original [synthetic fixture](../../examples/README.md) remains an opaque
byte-preservation example; its custom `catalog.json` is not an input to the
experimental ChatGPT parser. The separate paired mapping fixtures in
`tests/fixtures/chatgpt_exports.py` exercise the implemented semantic contract
and calculate conversation, revision, branch, project, and artifact outcomes.

