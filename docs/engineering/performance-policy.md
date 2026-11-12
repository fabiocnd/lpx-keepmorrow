# Performance Policy

**Owner:** Lopix Neural Inc.  
**Engineering lead:** Fabio de Sousa Lopes  
**Effective date:** 2026-11-12  
**Status:** Required methodology for performance-sensitive work

LPX Keepmorrow prioritizes correct preservation and verifiable recovery. A
performance optimization must retain those properties. No production throughput,
latency, memory, or cost target has been approved in this foundation.

## Define the workload before choosing a target

Describe the workload in measurable terms: total input bytes, file count, file
size distribution, message count, branch count, duplicate ratio, catalog size,
path depth, and compression or transfer conditions where relevant. Distinguish
many small files from a few large files; they exercise different costs.

Include supported boundary cases and adversarial shapes when they could alter
resource use. Use synthetic or explicitly authorized material. A benchmark must
not upload user archives or retain sensitive source content by default.

Set a numerical acceptance budget only when the operating environment and
workload justify it. Label an initial budget as a proposed target until it is
accepted. Do not present an aspirational target as an observed measurement.

## State resource complexity honestly

For an operation, define variables such as `B` for payload bytes, `F` for stored
files, and `C` for copy-buffer bytes. Explain the significant costs. A streaming
file pass may use `O(B)` work and `O(C)` payload memory, while inventory records
still require `O(F)` metadata memory. Sorting paths may add `O(F log F)` work.

Include extra passes, duplicate buffers, serialization, integrity checks, and
temporary disk use. A function's time complexity alone does not characterize
end-to-end performance. Do not remove a necessary verification pass without an
equivalent integrity argument and test evidence.

## Establish a reproducible measurement

A performance report must record:

| Item | Required detail |
| --- | --- |
| Source | Commit, implementation configuration, and benchmark command |
| Runtime | Interpreter or compiler version and relevant dependency versions |
| Machine | OS, architecture, CPU, memory, and storage characteristics |
| Dataset | Generator or fixture version, seed where used, and workload sizes |
| Conditions | Concurrency, cache state, warm-up, background load, and I/O location |
| Procedure | Number of repetitions, timing scope, failures, and excluded runs |
| Results | Measured values, variability, units, and observed limitations |
| Comparison | Same-workload baseline and explanation of material differences |

Measure wall time for user-visible duration. Measure peak memory and temporary
disk space when those resources could constrain the operation. Throughput must
state whether bytes are logical input, copied payload, compressed output, or
network traffic. Report quantiles only when the sample supports them; a handful
of runs does not justify a precise tail-latency claim.

## Optimize from evidence

Profile the complete relevant path before optimizing a presumed bottleneck.
Prefer eliminating redundant work, unnecessary allocation, avoidable copies,
and unsuitable data structures before adding concurrency or native code.

When reevaluating an existing design, account for every significant pass over
input and output bytes, inventory scans, path validation, catalog sorting, and
digest verification. Compare the measured result with the documented contract
before deciding whether work is redundant. Reading bytes again may be necessary
to establish a separate verification stage.

Keep performance-critical responsibilities cohesive so ownership and data flow
remain inspectable. Moving work into a separate service or language introduces
serialization, transfer, deployment, and failure costs; measure those costs
before adopting that boundary. Folder names alone do not establish architecture
or improve runtime performance.

Use bounded buffers, batches, queues, and workers where appropriate. Bound retry
work and ensure cancellation can be observed without corrupting completed work.
For caches, define key correctness, invalidation, memory bounds, and privacy
behavior. Demonstrate that a cache hit cannot conceal changed source bytes.

Compare the changed implementation with the baseline under equivalent conditions
and rerun relevant correctness checks. Record an inconclusive result as
inconclusive. Keep a slower approach when its measured cost is acceptable and
it materially improves correctness or maintenance.

## Automation and release claims

Unit tests are not throughput benchmarks. Performance checks should be added
only when they can detect a meaningful regression with stable workloads and a
justified tolerance. Timing-sensitive assertions on shared CI machines require
careful interpretation and should not replace controlled measurements.

This policy does not claim that a benchmark suite or performance gate is already
installed. Record actual tools and measured baselines as they are introduced.
Every public performance claim must identify the relevant version, workload,
environment, and measurement limits.
