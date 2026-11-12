# Foundation Verification Record

**Date:** 2026-11-12  
**Status:** Private source upload verified; Windows portability correction awaiting CI verification

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

Inventory now obtains complete metadata with `os.stat(..., follow_symlinks=False)`.
All six source-mutation signature fields remain checked. Two behavioral
regressions cover incomplete directory-entry metadata and replacement of a source
file after inventory, including refusal and staging cleanup.

The full local command above passed **40 tests with no failures or skips** after
this correction. A successful Windows rerun has not yet been established by this
version of the record.

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

- Windows publication behavior is implemented but has not been executed locally.
- The initial Windows CI failure is corrected locally; remote verification of
  the correction remains pending.
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
