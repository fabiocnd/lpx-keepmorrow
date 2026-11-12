# Foundation Verification Record

This is the historical 0.1.0 record. Its counts, capability limits, commits, and
measurements apply to that version. See the
[collection verification record](collection-verification.md) for 0.2.0.

**Date:** 2026-11-12
**Status:** Private source upload, local validation, and configured CI matrix verified

**Environment:** Linux x86_64, Python 3.12.14

## Executed validation

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

Initial source result: **38 tests passed**, with no skips or failures in this environment.

The executed scenarios cover byte-identical recovery, deterministic manifests,
empty files and directories, corruption, missing and unexpected inventory,
existing-destination refusal, atomic no-replace publication, symbolic links,
unsafe paths, resource bounds, staging cleanup, CLI status, and consent refusal
before selected-data access.

The consent tests exercise all three user commands and missing, partial, stale,
and malformed declarations. They verify that archive services and filesystem
inspection are not called when acceptance is refused.

JSON documents, TOML configuration, and Python source syntax were parsed
successfully. A repository-local Markdown link check found no missing targets
in the reviewed document set. A focused pattern check found no exposed private
keys, known token prefixes, or unrelated personal contact/address details.
This is a bounded review, not a certification that all possible secrets or
security defects are absent.

## Windows portability correction

The [initial CI run](https://github.com/fabiocnd/lpx-keepmorrow/actions/runs/43207182721)
passed on Ubuntu with Python 3.11 and 3.14, but failed on both Windows jobs.
Directory-entry metadata on Windows omitted the device and file identifiers
needed for comparison with an opened file descriptor. Valid source files were
therefore incorrectly rejected as changed after inventory.

The first correction used complete no-follow path metadata. Its
[CI run](https://github.com/fabiocnd/lpx-keepmorrow/actions/runs/43207866542)
passed on both Ubuntu jobs and Windows with Python 3.11, while Windows with
Python 3.14 still failed. The remaining issue was incompatible path and
descriptor change-time semantics, documented in
[CPython issue 157671](https://github.com/python/cpython/issues/157671).

Windows inventory now obtains regular-file metadata from an opened descriptor.
Before accepting that metadata, it binds the no-follow path observation to the
descriptor using device and inode identity, size, modification time, and mode.
Only filename-derived execute bits are excluded from that cross-API mode
comparison. File type and read/write bits remain checked. All six fields of the
full descriptor signature remain checked after inventory and during reads.

Regressions cover incomplete directory-entry metadata, divergent timestamp and
mode semantics, replacement during and after inventory, staging cleanup, and
byte-preserving round trips for executable filename extensions without executing
their contents. The full local command above passed **42 tests with no failures
or skips** after these corrections. The remote matrix results are recorded below.

The Windows inventory requires one additional metadata-only open/stat/close
cycle per regular file per scan, with one additional handle at a time. The Linux
metadata path is unchanged. No Windows performance measurement is claimed.

## Verified CI matrix

[Reference Core run 43209022326](https://github.com/fabiocnd/lpx-keepmorrow/actions/runs/43209022326)
completed successfully for source commit
[`9f8cd88826e1d57fcb1c48a47752a05a64fbe166`](https://github.com/fabiocnd/lpx-keepmorrow/commit/9f8cd88826e1d57fcb1c48a47752a05a64fbe166).
All four jobs passed Python syntax validation and behavioral tests.

| Runner | Python | Passed | Skipped | Outcome |
| --- | --- | --- | --- | --- |
| Ubuntu | 3.11 | 42 | 0 | Success |
| Ubuntu | 3.14 | 42 | 0 | Success |
| Windows | 3.11 | 40 | 2 | Success |
| Windows | 3.14 | 40 | 2 | Success |

Each job enumerated 42 tests. The Windows logs identify two expected platform
skips: named pipes were unavailable, and the filesystem was case insensitive,
preventing construction of the case-sensitive filename-collision scenario.
These scenarios executed successfully on Ubuntu. The skipped Windows scenarios
are not reported as executed or passed.

The result applies to the exact source revision and hosted environments above.
Subsequent documentation updates do not expand its platform or workload scope.

## Measured performance

The committed [benchmark result](../../benchmarks/results/2026-11-12-linux-reference.json)
records a synthetic 32 MiB workload: eight 4 MiB files, three repetitions.

| Operation | Median elapsed time |
| --- | --- |
| Create and validate | 0.1540 seconds |
| Verify | 0.03180 seconds |
| Restore and validate | 0.1899 seconds |

The highest observed Python-tracked allocation was approximately 2.02 MiB.
These are warm-cache shared-development measurements, include instrumentation
overhead, and do not measure total process RSS. Storage hardware and dedicated
CPU allocation were not characterized. No production throughput target is
established.

## Reviewed limitations

- Local execution used Linux; Windows execution evidence comes from the hosted
  CI matrix and includes the two documented platform skips.
- No hostile concurrent ancestor-replacement defense or fsync crash-durability
  guarantee is implemented.
- Source conversations and native project relationships are not semantically
  parsed by this byte-preservation reference.
- No remote transfer, model integration, source-deletion operation, or durable
  job engine is present.
- Acceptance receipts are local declaration metadata, not authenticated legal
  evidence or a persistent consent ledger.
- The legal documents remain drafts for owner and qualified Ontario counsel
  review. Tests do not establish enforceability.

## Remote status

On 2026-11-12, authenticated GitHub metadata confirmed that the user-created
[fabiocnd/lpx-keepmorrow](https://github.com/fabiocnd/lpx-keepmorrow) repository
was private. The initial upload contained all 64 tracked source files. At
verification time, `main` pointed to the remote commit recorded below.

| Evidence | Verified value |
| --- | --- |
| Repository ID | `1455189876` |
| Verification date | `2026-11-12` |
| Visibility | Private |
| Tracked files uploaded | 64 |
| Remote source commit | `e01ccf12b849bef742cd53b7d1ea2f23b21a0f28` |
| Local source snapshot commit | `ab4eb2bd531398edb8f33f225ced5f14e1562293` |
| Matching remote and local Git tree | `36a2c9dc3b3eb89fcc62a9ce92948a86c3eb74e8` |

The remote Git tree matched the local `git write-tree` result exactly. These
identifiers record the verified initial source upload; later documentation
commits may advance `main`. Source delivery does not establish CI execution or
an implemented remote archive-transfer capability. CI evidence is recorded
separately above.

The GitHub connector does not expose author or committer fields. Its remote
commit records Fabio Lopes under a GitHub-managed noreply identity, while a
commit trailer credits `Fabio de Sousa Lopes <fabio@lopixneural.com>`. That
trailer does not replace the primary author or committer metadata. The local
source snapshot and repository-local Git configuration retain the canonical
project identity, `Fabio de Sousa Lopes <fabio@lopixneural.com>`.
