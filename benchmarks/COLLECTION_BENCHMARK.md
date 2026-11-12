# Collection Reference Benchmark

This reproducible local experiment measures the semantic collection workflow on
synthetic data. It establishes an initial observation, not a release target or
a comparison with the official ChatGPT exporter. No earlier semantic-collection
performance baseline exists.

## Reproduce

From the repository root:

```bash
PYTHONPATH=src python benchmarks/benchmark_collection.py --conversations 100 --messages 12 --repetitions 3 --output benchmarks/results/2026-11-12-collection-reference.json
```

The generator is self-contained and uses only the standard library and the
Keepmorrow source. It does not import test fixtures, access an account, or use
the network. Conversation count, initial message count, and repetition count
are configurable. Archive, parser, and catalog resource limits still apply.

## Workload and measurement boundary

The observed run used 100 logical conversations with 12 initial messages each,
plus structural root nodes. The second capture renames 50 conversations, changes
an unknown source field, and adds a follow-up message and an alternative branch.
The resulting collection contains 150 revisions, 200 capture occurrences, 2,050
graph nodes, and 50 branched revisions.

The first capture is a directory. The second is a deflated ZIP with fixed
timestamps. Each contains a 2 MiB binary payload and a valid 70-byte PNG; the
second binary differs from the first. The seven expanded source files total
5,021,394 bytes. Submitted input totals 2,514,306 bytes, including the 16,484-byte
ZIP. This deliberately compressible corpus does not represent arbitrary media.

Each of three repetitions measures:

1. Initial import of the first directory into a new archive.
2. Extension with the second ZIP, copying prior captured payload into a separate
   immutable generation.
3. Verified catalog loading and literal search. Loading currently verifies all
   archived bytes before trusting the derived catalog.
4. Recovery of one evolving conversation and its bound binaries into a separate
   portable archive.

Fixture generation, ZIP construction, and supplemental checks are outside the
timed regions. The services' own verification remains inside the measurements.
Supplemental checks established every expected count, identical generated
manifests across repetitions, unchanged parent manifests, selected-scope
recovery without whole source JSON or ZIP containers, and 24 exact binary hash
comparisons across full and selected collections.

## Observed results

Measured on November 12, 2026, at 12:37 UTC, with CPython 3.12.14 on Linux x86-64. The environment
reported an AMD EPYC 9V74 CPU and nine logical CPUs. Storage medium, CPU quota,
and effective memory capacity were not characterized.

| Stage | Median seconds | Observed seconds range | Maximum Python-traced peak bytes |
| --- | ---: | ---: | ---: |
| Initial import | 0.617440 | 0.580659–0.622769 | 4,893,062 |
| Extend generation | 1.051870 | 1.026765–1.057551 | 11,318,444 |
| Verified catalog and search | 0.369093 | 0.341649–0.375520 | 4,491,014 |
| Selected recovery | 0.412937 | 0.401102–0.415453 | 4,491,464 |

Timing includes `tracemalloc` overhead. Traced allocation peaks are **not process
RSS** and exclude operating-system caches and some native allocations. Garbage
collection runs before each measured operation. Filesystem caches are not
flushed; generation, previous stages, and repeated reads warm the cache. Three
repetitions support the reported medians and observed ranges, not tail-latency
or production-capacity claims.

## Wide-branch diagnostic

A separate measurement validates already parsed catalogs containing one parent
with 1,000 or 4,000 children. Import, disk verification, and rendering are outside
this diagnostic's timed region. Median validation time was 0.071033 seconds for
1,002 total nodes and 0.282333 seconds for 4,002 total nodes: 3.97 times the time
for four times the branch width. Maximum traced peaks were 354,183 and 1,403,015
bytes, respectively.

This size comparison helps inspect broad-graph validation costs without a
fragile CI timing threshold. It does not prove asymptotic behavior or establish
a speed improvement over an earlier implementation.

## Source attribution and limitations

The [machine-readable report](results/2026-11-12-collection-reference.json)
contains every sample, environment detail, generated source digest, and SHA-256
of relevant implementation files and the benchmark script. Its source aggregate
is `d9789f2f86ea858bca6255cbde1ff12e55b56228a23fef108ed17054e4deac44`.
The source was unchanged between the beginning and end of this run. These are
worktree file hashes; no unverified commit equivalence is asserted.

The current immutable-generation design copies prior payload rather than
sharing content-addressed blobs. Queries pay full archive verification cost.
Those costs are part of the observed behavior. Real-export compatibility,
large-corpus behavior, cold storage, Windows performance, remote transport,
crash durability, and authenticated integrity are outside this experiment.
Rerun the command after implementation changes before attributing these numbers
to the revised source.
