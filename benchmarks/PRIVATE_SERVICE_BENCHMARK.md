# Private Service Reference Benchmark

This experiment exercises `PreservationService`, its real authorization and
operation stores, the single worker, binary staging, and verified delivery with
synthetic data. It records an internal service baseline. HTTP transport, browser
interaction, OAuth providers, and the ChatGPT host are outside the measurement.

## Reproduce

From the repository root:

```bash
python benchmarks/benchmark_private_service.py --conversations 250 --nodes 12 --binary-mib 8 --repetitions 3 --timeout-seconds 120 --output benchmarks/results/2026-11-12-private-service-reference.json
```

The standard-library driver launches one fresh Python subprocess and runs three
workflows through one service instance. The first pass has no earlier service
workflow in that process. The next two reuse the interpreter, worker, and ledger;
earlier uploads, outputs, and grants remain present. Fixture generation occurs
inside the child before the first pass and can warm its allocator and the
filesystem cache. **No pass establishes a cold filesystem.** Shared-host load and
storage medium are not controlled.

The default workload contains 250 conversations with 12 graph nodes each: one
structural root and 11 message nodes. Fifty conversations contain an alternative
branch. Three project identities are explicit. A single 8 MiB binary has 250
attachment references. A deterministic, non-ZIP64 `ZIP_STORED` container holds
the JSON export and binary; the simple binary pattern does not inflate a
compression-based throughput claim. Recovery selects ten explicit conversation
identities and their bound binary.

## Measurement boundaries

Each pass uploads the input stream, imports it, performs bounded browse, literal
search, and revision reads, creates a selected recovery, packages it, downloads
the verified ZIP to a new local file, stages that package again, and unpacks it.
Supplemental validation compares the selected identities, original submitted
ZIP, recovered binary digest, and unchanged recovery manifest bytes.

Authorization grants and plan reviews are inserted by the isolated benchmark
driver. They exercise persistence and authorization costs; **they are synthetic
records and provide no evidence of a person's acceptance or approval**. Operation
durations include preparation, this synthetic review persistence, enqueueing,
worker execution, verification, and terminal-status polling. Separate synthetic
grant stages are recorded. Read queries include the service's complete archive
and catalog validation. Download includes package revalidation, local streaming
copy, and SHA-256; it does not measure network transfer.

While an operation is nonterminal, the driver measures authorized status and
collection-reference listing calls. These calls inspect control metadata and do
not acquire the content-I/O slot. The report distinguishes samples whose
preceding status observed an active worker from all nonterminal samples; state
can change during either call. A 10 ms polling interval contributes to measured
operation duration. Content-admission retries are counted when final scratch
cleanup briefly retains the content-I/O slot after terminal status is visible.

An independent thread samples regular-file logical sizes and `st_blocks`
allocation every 50 ms. Each stage records before/after inventories, sampled
maxima, and a compact total/scratch timeline. Scans never read file content or
follow symlinks. They are non-atomic: short-lived files can be missed, and a
concurrently renamed file can appear twice in a scan. These are **observed disk
figures**, not proven peaks or allocation limits. Directory and filesystem
metadata are excluded. Category maxima can occur at different times and should
not be added together. Concurrent sampling overhead is inside the timed stages;
the initial and final scans are outside each stage timer but inside the complete
workflow timer.

The child reports its actual cumulative process peak RSS through
`resource.getrusage(resource.RUSAGE_SELF)`. Linux reports KiB, which the driver
converts to bytes. RSS includes fixture generation and measurement threads;
it is not an isolated per-stage allocation result. `tracemalloc` is disabled.
Application imports, fixture generation, service setup, every raw stage sample,
and the parent-observed child wall time are separately recorded.

## Observed reference run

The [machine-readable report](results/2026-11-12-private-service-reference.json)
was recorded on November 12, 2026, at 14:51 UTC. It used CPython 3.12.14,
SQLite 3.53.1, and Linux 6.18.57 on x86-64. The host reported an AMD EPYC 9V74
processor and nine logical CPUs. Effective CPU/memory quotas and storage medium
were not characterized. The temporary filesystem reported 5,222,326,272 available
bytes before setup; this is an observed free-space value, not a storage budget.

The two expanded source files totaled 9,162,409 bytes. The submitted ZIP contained
9,162,657 bytes; each selected recovery ZIP contained 8,499,788 bytes. All three
packages had SHA-256
`30a1b8916598bcfe034078ee4678bba6d467301205dd2de487eef80f078acb0a`.
Each pass verified the ten selected identities, original ZIP bytes, 8 MiB binary
digest, and unchanged recovery manifest. The twelve journaled operations returned
three `completed` imports and nine `partial` recovery/package/unpack results with
`selection_omissions` coverage. Those partial outcomes describe the selected scope.

| Stage | First pass, seconds | Subsequent-pass median, seconds | Observed range across three passes, seconds |
| --- | ---: | ---: | ---: |
| Input upload | 0.012842 | 0.038052 | 0.012842–0.047101 |
| Import | 0.619985 | 0.566773 | 0.516741–0.619985 |
| Browse query | 0.131838 | 0.144405 | 0.131838–0.154082 |
| Search query | 0.118620 | 0.132469 | 0.118620–0.135619 |
| Read query | 0.108358 | 0.126069 | 0.108358–0.127406 |
| Selected recovery | 0.306346 | 0.346596 | 0.306346–0.353973 |
| Recovery packaging | 0.229306 | 0.237575 | 0.229306–0.242954 |
| Verified local download | 0.081196 | 0.119806 | 0.081196–0.122626 |
| Recovery upload | 0.014182 | 0.010592 | 0.010187–0.014182 |
| Unpack | 0.105885 | 0.113994 | 0.105885–0.121859 |
| Supplemental round-trip validation | 0.027875 | 0.031651 | 0.027875–0.032872 |

Complete workflow times were **1.800037, 1.974448, and 1.957537 seconds**. The
subsequent-pass median was 1.965993 seconds. Complete workflow timing also includes
the separately recorded synthetic grant stages and sampling overhead outside the
individual stage timers. The parent observed 6.013337 seconds for the child,
including imports, fixture creation, service setup, and cleanup. The child-process
peak RSS was **34,865,152 bytes (33.25 MiB)**. A later pass being slower does not
identify a cause: cache residency, retained ledger size, and shared-host load were
not isolated.

There were 113 control-plane observations whose preceding status showed active
work. Status calls had a median of **2.424 ms** and observed range of
0.856–234.812 ms. Collection-reference listing had a median of **2.455 ms** and
observed range of 0.347–103.333 ms. The maxima remain visible because these data
do not justify a blanket claim of uniformly low latency or a tail percentile.

The largest sampled scratch logical size was **27,487,694 bytes**. The largest
sampled total was **242,373,708 logical bytes / 242,556,928 allocated bytes**,
including fixtures, downloads, retained outputs, staging, and control metadata.
After all three passes and worker shutdown, those regular files totaled
236,093,403 logical bytes; scratch contained zero files and zero bytes. Two
paths disappeared during concurrent scans; other scan errors were not observed
in this run. These observations retain the non-atomic sampling limits above and
do not replace the service's conservative admission reservations.

## Source attribution and scope

The machine-readable report records SHA-256 for every `src/**/*.py` file and the
benchmark script, plus a canonical aggregate digest. It separately records the
exact policy-file hashes and versions. Source hashes are checked again after
measurement; the driver refuses to write a reference file when they changed.
UI bundles are excluded because this experiment does not load the UI. Worktree
hashes identify the measured implementation without claiming equivalence to an
unverified commit.

The recorded source aggregate is
`1bb967e14376b708f52b19f7fc5952ebb3e624900ab5792ea52d56df87d990fb`,
covering 51 Python files including the driver. Source hashes matched before and
after the run. The policy versions were `2026-11-12-draft.3`; their exact hashes
appear independently in the report. This measurement makes no claim that those
drafts received legal review or actual human acceptance.

Three modest passes support raw values, medians, and observed ranges. They do
not establish tail latency, concurrency capacity, a general speed improvement,
production reliability, or operation at the configured storage ceilings. The
service's normal `partial` outcome for a selected recovery preserves its explicit
`selection_omissions` scope; it is distinct from an execution failure.

Rerun after implementation changes before attributing a result to the revised
source. This service benchmark and the collection benchmark have different
workloads, verification boundaries, and allocation instrumentation; their times
are not a controlled comparison.
