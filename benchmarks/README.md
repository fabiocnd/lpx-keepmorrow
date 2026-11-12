# Reference Archive Benchmark

Run from the repository root:

```bash
python benchmarks/benchmark_archive.py --files 8 --mib-per-file 4 --repetitions 3
```

The script creates its own synthetic data in a temporary directory, measures create, verify, and restore independently, and removes the generated data on normal completion. It does not accept private source files or call a model or network service. It invokes internal archive primitives as a development experiment; the product CLI's agreement boundary remains separate.

JSON output records Python version, OS, machine architecture, exact workload, repetitions, per-stage wall times, Python allocation peaks, and median wall times. The measurement includes `tracemalloc` overhead. It does not measure total process RSS, flush the filesystem cache, perform `fsync`, establish cold-storage performance, or certify a release budget. Logical throughput divides original source bytes by elapsed time; create and restore also read copies for verification, so this is not physical storage bandwidth.

Use separate workloads for many small files and a few large files. Keep the storage medium, available space, hardware, Python version, background workload, and cache policy comparable before interpreting differences. Repetitions retain prior generated archives until the temporary directory closes, so available disk space must cover the source plus two copies per repetition. Follow the [performance policy](../docs/engineering/performance-policy.md) for evidence required before making a product performance claim.

The [2026-11-12 Linux reference run](results/2026-11-12-linux-reference.json) records one completed 32 MiB synthetic experiment on Python 3.12.14. Its measurements describe that shared development environment and workload only; storage hardware and dedicated CPU allocation were not characterized, so it is not a production baseline.

