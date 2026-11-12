"""Measure the complete reference archive lifecycle on synthetic local data.

This is a reproducible experiment, not a release performance certification.
Copyright 2026 Lopix Neural Inc. All rights reserved.
"""

from __future__ import annotations

import argparse
import json
import platform
import statistics
import sys
import tempfile
import time
import tracemalloc
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from keepmorrow.archive import create_archive, restore_archive, verify_archive  # noqa: E402


def positive_int(value: str) -> int:
    result = int(value)
    if result <= 0:
        raise argparse.ArgumentTypeError("The value must be a positive integer.")
    return result


def measure(operation: Callable[[], object]) -> tuple[float, int]:
    """Return wall time and peak Python-traced bytes for a successful call.

    Tracing overhead is included in elapsed time. The allocation peak excludes
    process memory outside tracemalloc and must not be reported as peak RSS.
    """
    tracemalloc.start()
    start = time.perf_counter()
    operation()
    elapsed = time.perf_counter() - start
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return elapsed, peak


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--files", type=positive_int, default=8)
    parser.add_argument("--mib-per-file", type=positive_int, default=4)
    parser.add_argument("--repetitions", type=positive_int, default=3)
    args = parser.parse_args()
    byte_count = args.files * args.mib_per_file * 1024**2
    if args.files > 10_000 or args.mib_per_file > 2048 or byte_count > 10 * 1024**3:
        parser.error("The workload exceeds the reference core's default limits.")
    results: dict[str, list[dict[str, float | int]]] = {name: [] for name in ("create", "verify", "restore")}
    with tempfile.TemporaryDirectory(prefix="keepmorrow-benchmark-") as temporary:
        root = Path(temporary).resolve()
        source = root / "source"
        source.mkdir()
        block = bytes(range(256)) * 4096
        for index in range(args.files):
            with (source / f"file-{index:06d}.bin").open("wb") as output:
                for _ in range(args.mib_per_file):
                    output.write(block)
        for repetition in range(args.repetitions):
            archive = root / f"archive-{repetition}"
            restored = root / f"restored-{repetition}"

            def verify_checked() -> object:
                result = verify_archive(archive)
                if not result.verified:
                    raise RuntimeError("The benchmark archive failed verification.")
                return result

            operations = {
                "create": lambda: create_archive(source, archive),
                "verify": verify_checked,
                "restore": lambda: restore_archive(archive, restored),
            }
            for name, operation in operations.items():
                elapsed, peak = measure(operation)
                results[name].append({"seconds": elapsed, "python_peak_bytes": peak,
                                      "logical_mib_per_second": byte_count / 1024**2 / elapsed})
    print(json.dumps({
        "measured_at": datetime.now(timezone.utc).isoformat(),
        "python": platform.python_version(),
        "platform": platform.system(),
        "machine": platform.machine(),
        "workload": {"files": args.files, "bytes_per_file": args.mib_per_file * 1024**2,
                     "total_bytes": byte_count, "repetitions": args.repetitions},
        "measurement_notes": [
            "Wall time includes tracemalloc overhead; allocation peaks cover Python-tracked memory only.",
            "Filesystem cache is not flushed. This is a warm-cache local experiment.",
            "Logical throughput uses source byte count; create and restore perform additional verification reads.",
            "No fsync, cold-storage measurement, remote transfer, or release guarantee is represented.",
        ],
        "samples": results,
        "median_seconds": {name: statistics.median(sample["seconds"] for sample in samples)
                           for name, samples in results.items()},
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

