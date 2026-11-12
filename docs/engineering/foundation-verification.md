# Foundation Verification Record

**Date:** 2026-11-12  
**Status:** Local foundation verified; remote repository publication not yet verified  
**Environment:** Linux x86_64, Python 3.12.14

## Executed validation

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

Result: **38 tests passed**, with no skips or failures in this environment.

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
- CI is configured; remote execution is not established by this record.
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

The authenticated GitHub connector identified `fabiocnd`. The repository
creation operation is not exposed by that connector. Browser authentication
was started for private repository creation and requires completion before
remote existence, privacy, source upload, or CI can be reported as verified.
