# Performance and Organization Review

**Review date:** 2026-11-12  
**Scope:** Foundation design and local reference implementation.

## Engineering assessment

The project's highest-risk operation is preserving and recovering the correct
bytes under a clearly stated scope. The first implementation therefore gives
priority to deterministic behavior, predictable resource use, and visible
failure. A complex distributed system or an AI-first pipeline would add costs
before these invariants are proven.

The repository grouping in [ADR 0001](../architecture/decisions/0001-repository-layout.md)
supports this work by keeping file integrity, consent, product semantics, and
future integration boundaries distinct.

## Decisions applied to the foundation

| Concern | Approach | Evidence needed |
| --- | --- | --- |
| Large files | Fixed-buffer streaming for hashing and copy | Large-file workload with peak memory measurement |
| Many small files | Explicit entry limits and canonical inventory | File-count sweep and manifest-size measurement |
| Repeated work | Deterministic manifest for identical input | Repeated-capture test; no logical deduplication claim |
| Cross-platform recovery | Portable path rules and collision checks | Windows and Linux CI plus hostile-path fixtures |
| Failed writes | Temporary staging and separate destination | Injected failures leave source unchanged and no false success |
| Corruption | SHA-256 comparison and inventory reconciliation | Deliberately changed and missing files are detected |
| Consent | Gate user-facing operations before data access | Decline and stale-version tests prove no processing |
| Model overhead | No model calls in preservation operations | Dependency and call-path review |
| Runtime complexity | One small package with no runtime dependencies | Import, tests, and CLI work without package downloads |

## What is deliberately not claimed

No throughput objective, low-latency percentile, bounded total RSS, filesystem
race-proof guarantee, or production-scale result is asserted without measurement.
A fixed I/O buffer does not make total process memory constant: inventory,
sorting, JSON parsing, interpreter state, and diagnostics consume additional
memory.

A byte hash is not a logical conversation identity. Deterministic snapshots
do not implement resumable jobs, semantic deduplication, or incremental backups.

## Benchmark methodology

Use the committed benchmark harness with an explicitly recorded file count,
total bytes, size distribution, repetition count, Python version, OS, CPU,
storage assumptions, and cache limitations. Report operation duration and
throughput together with the workload. Keep correctness checks enabled.

Separate fixture construction from measured operations. A median from repeated
local runs is an observation, not a production service-level objective.
Record whether peak memory is Python allocator memory or process RSS.

## Next optimizations, gated by evidence

1. Measure many-small-file and few-large-file workloads independently.
2. Determine whether parsing, directory metadata, hashing, copying, or verification
   dominates the target workload.
3. Evaluate avoiding duplicate reads without weakening integrity checks.
4. Set explicit performance budgets for an identified deployment.
5. Introduce bounded concurrency only when sequential I/O is a measured bottleneck.
6. Revisit manifest representation when the entry-count limit becomes restrictive.

Each optimization must preserve byte identity, failure reporting, determinism,
and authorization. A faster incorrect archive is not a successful result.
