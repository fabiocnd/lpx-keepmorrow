"""Measure immutable collection generations using self-contained synthetic data.

Timings include Python allocation tracing. The report identifies the source
files that were actually present, rather than attributing an uncommitted tree
to an unrelated commit. This experiment makes no comparative speed claim.

Copyright 2026 Lopix Neural Inc. All rights reserved.
"""

from __future__ import annotations

import argparse
import base64
import copy
from datetime import UTC, datetime
import gc
import hashlib
import json
import os
from pathlib import Path
import platform
import stat
import statistics
import sys
import tempfile
import time
import tracemalloc
from typing import Any, Callable
import zipfile
import zlib

REPOSITORY = Path(__file__).resolve().parents[1]
GENERATOR_VERSION = 1
NAMESPACE = "synthetic-benchmark-account"
PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGNQcEj4DwADBAHAgChw2gAAAABJRU5ErkJggg=="
)
BINARY_BYTES_PER_CAPTURE = 2 * 1024**2
WIDE_BRANCH_WIDTHS = (1_000, 4_000)


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("The value must be a positive integer.")
    return parsed


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while block := source.read(1024**2):
            digest.update(block)
    return digest.hexdigest()


def _json_digest(document: object) -> str:
    return hashlib.sha256(json.dumps(document, sort_keys=True,
                                    separators=(",", ":")).encode("utf-8")).hexdigest()


def _source_reference() -> dict[str, Any]:
    paths = sorted((REPOSITORY / "src/keepmorrow").rglob("*.py"))
    paths.append(Path(__file__).resolve())
    files = {path.relative_to(REPOSITORY).as_posix(): _hash_file(path) for path in paths}
    return {"kind": "worktree_file_sha256", "aggregate_sha256": _json_digest(files), "files": files}


def _optional_text(path: str, maximum: int = 8192) -> str | None:
    try:
        with Path(path).open("r", encoding="utf-8") as source:
            return source.read(maximum).strip()
    except (OSError, UnicodeError):
        return None


def _environment() -> dict[str, Any]:
    cpu_model = platform.processor() or None
    cpu_info = _optional_text("/proc/cpuinfo", 65536)
    if cpu_info:
        cpu_model = next((line.split(":", 1)[1].strip() for line in cpu_info.splitlines()
                          if line.startswith("model name") and ":" in line), cpu_model)
    return {
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "python_build": list(platform.python_build()),
        "operating_system": platform.system(), "release": platform.release(),
        "platform": platform.platform(), "architecture": platform.machine(),
        "cpu_model": cpu_model, "logical_cpus_reported_by_os": os.cpu_count(),
        "linux_cgroup_cpu_max": _optional_text("/sys/fs/cgroup/cpu.max"),
        "linux_cgroup_memory_max": _optional_text("/sys/fs/cgroup/memory.max"),
        "zlib_compile_version": zlib.ZLIB_VERSION,
        "zlib_runtime_version": zlib.ZLIB_RUNTIME_VERSION,
        "temporary_storage": "Host default TemporaryDirectory storage; medium and cache residency are not characterized.",
    }


def _message(identifier: str, role: str, text: str) -> dict[str, Any]:
    return {"id": identifier, "author": {"role": role},
            "content": {"content_type": "text", "parts": [text]}}


def _source_record(index: int, messages: int) -> dict[str, Any]:
    nodes: dict[str, Any] = {
        "root": {"id": "root", "parent": None, "children": ["node-000001"], "message": None}
    }
    for offset in range(1, messages + 1):
        node_id = f"node-{offset:06d}"
        parent = "root" if offset == 1 else f"node-{offset - 1:06d}"
        children = [f"node-{offset + 1:06d}"] if offset < messages else []
        text = f"Synthetic conversation {index:06d}, message {offset:06d}: preserve supplied evidence."
        if offset == messages:
            text += " benchmark-search-marker"
        message = _message(f"message-{offset:06d}", "user" if offset % 2 else "assistant", text)
        if offset == 1:
            message["metadata"] = {"attachments": [
                {"id": "binary-evidence", "relative_path": "assets/evidence.bin",
                 "name": "evidence.bin", "mime_type": "application/octet-stream"},
                {"id": "image-evidence", "relative_path": "assets/pixel.png",
                 "name": "pixel.png", "mime_type": "image/png"},
            ]}
        nodes[node_id] = {"id": node_id, "parent": parent, "children": children, "message": message}
    return {
        "id": f"conversation-{index:06d}", "title": f"Synthetic preservation topic {index:06d}",
        "project_id": f"project-{index % 2 + 1}", "mapping": nodes,
        "current_node": f"node-{messages:06d}",
        "future_metadata": {"generator_version": GENERATOR_VERSION, "opaque_revision": 1},
    }


def _write_corpus(root: Path, conversations: int, messages: int) -> tuple[Path, Path, Path, dict[str, Any]]:
    first, second = root / "export-first", root / "export-second"
    first.mkdir()
    second.mkdir()
    records = [_source_record(index, messages) for index in range(conversations)]
    revised = copy.deepcopy(records)
    evolved = 0
    for index, record in enumerate(revised):
        if index % 2:
            continue
        evolved += 1
        record["title"] += " — reviewed"
        record["future_metadata"]["opaque_revision"] = 2
        nodes = record["mapping"]
        last = f"node-{messages:06d}"
        nodes[last]["children"].append("follow-up")
        nodes["follow-up"] = {
            "id": "follow-up", "parent": last, "children": [],
            "message": _message("message-follow-up", "assistant", "A later source revision adds new evidence."),
        }
        nodes["node-000001"]["children"].append("alternative")
        nodes["alternative"] = {
            "id": "alternative", "parent": "node-000001", "children": [],
            "message": _message("message-alternative", "assistant", "Retain the alternative branch."),
        }
        record["current_node"] = "follow-up"
    (first / "conversations.json").write_text(json.dumps(records, ensure_ascii=False), encoding="utf-8", newline="\n")
    split = (conversations + 1) // 2
    for index, portion in enumerate((revised[:split], revised[split:]), 1):
        (second / f"conversations-{index}.json").write_text(
            json.dumps(portion, ensure_ascii=False), encoding="utf-8", newline="\n"
        )
    block = bytes(range(256)) * 4096
    for ordinal, directory in enumerate((first, second)):
        (directory / "assets").mkdir()
        with (directory / "assets/evidence.bin").open("wb") as output:
            for offset in range(0, BINARY_BYTES_PER_CAPTURE, len(block)):
                data = block[:min(len(block), BINARY_BYTES_PER_CAPTURE - offset)]
                if ordinal == 1 and offset == 0:
                    data = b"\xff" + data[1:]
                output.write(data)
        (directory / "assets/pixel.png").write_bytes(PNG_BYTES)
    container = root / "second-export.zip"
    with zipfile.ZipFile(container, "w") as archive:
        for path in sorted(second.rglob("*")):
            if not path.is_file():
                continue
            info = zipfile.ZipInfo(path.relative_to(second).as_posix(), date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (stat.S_IFREG | 0o600) << 16
            with path.open("rb") as source, archive.open(info, "w") as output:
                while chunk := source.read(1024**2):
                    output.write(chunk)
    file_inventory = {
        f"{label}/{path.relative_to(directory).as_posix()}": {
            "size_bytes": path.stat().st_size, "sha256": _hash_file(path)
        }
        for label, directory in (("first", first), ("second", second))
        for path in sorted(directory.rglob("*")) if path.is_file()
    }
    initial_bytes = sum(item["size_bytes"] for path, item in file_inventory.items() if path.startswith("first/"))
    workload = {
        "generator_version": GENERATOR_VERSION, "seed": "deterministic; no random generator",
        "conversations": conversations, "messages_per_initial_conversation": messages,
        "evolved_conversations": evolved, "captures": 2,
        "source_formats": ["directory", "zip_stored_or_deflated_profile"],
        "expanded_source_bytes": sum(item["size_bytes"] for item in file_inventory.values()),
        "submitted_input_bytes": initial_bytes + container.stat().st_size,
        "original_zip_bytes": container.stat().st_size,
        "source_file_count": len(file_inventory),
        "binary_payload_bytes_per_capture": BINARY_BYTES_PER_CAPTURE,
        "png_bytes_per_capture": len(PNG_BYTES),
        "source_files": file_inventory,
        "source_corpus_sha256": _json_digest(file_inventory),
        "original_zip_sha256": _hash_file(container),
        "expected_summary": {
            "capture_count": 2, "conversation_count": conversations,
            "revision_count": conversations + evolved, "occurrence_count": 2 * conversations,
            "message_node_count": conversations * (messages + 1) + evolved * (messages + 3),
            "branched_revision_count": evolved, "stored_artifact_references": 4 * conversations,
            "unavailable_artifact_references": 0,
        },
    }
    return first, second, container, workload


def _measure(operation: Callable[[], Any]) -> tuple[Any, dict[str, float | int]]:
    gc.collect()
    tracemalloc.start()
    started = time.perf_counter()
    try:
        result = operation()
        seconds = time.perf_counter() - started
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    return result, {"seconds": seconds, "python_traced_peak_bytes": peak}


def _statistics(samples: list[dict[str, float | int]]) -> dict[str, float | int]:
    return {
        "median_seconds": statistics.median(sample["seconds"] for sample in samples),
        "minimum_seconds": min(sample["seconds"] for sample in samples),
        "maximum_seconds": max(sample["seconds"] for sample in samples),
        "median_python_traced_peak_bytes": statistics.median(sample["python_traced_peak_bytes"] for sample in samples),
        "maximum_python_traced_peak_bytes": max(sample["python_traced_peak_bytes"] for sample in samples),
    }


def _check_binary_bytes(collection: Any, expected: dict[tuple[str, str], str]) -> int:
    checked = 0
    for capture in collection.document["captures"]:
        for record in capture["files"]:
            path = record["path"]
            if path not in {"assets/evidence.bin", "assets/pixel.png"}:
                continue
            key = capture["storage_id"], path
            target = collection.root / "payload/captures" / capture["storage_id"] / "source" / path
            actual = _hash_file(target)
            if actual != record["sha256"] or actual != expected[key]:
                raise RuntimeError("A benchmark binary did not match the exact supplied bytes.")
            checked += 1
    if checked != 4:
        raise RuntimeError("The benchmark did not recover every expected binary occurrence.")
    return checked


def _write_wide_export(root: Path, width: int) -> Path:
    directory = root / f"wide-source-{width}"
    directory.mkdir()
    children = [f"leaf-{index:06d}" for index in range(width)]
    mapping: dict[str, Any] = {
        "root": {"id": "root", "parent": None, "children": ["hub"], "message": None},
        "hub": {"id": "hub", "parent": "root", "children": children,
                "message": _message("hub-message", "user", "Retain every branch.")},
    }
    for child in children:
        mapping[child] = {"id": child, "parent": "hub", "children": [],
                          "message": _message(f"{child}-message", "assistant", "One synthetic alternative.")}
    record = {"id": "wide-conversation", "title": "Wide synthetic message graph",
              "mapping": mapping, "current_node": children[-1]}
    (directory / "conversations.json").write_text(json.dumps([record]), encoding="utf-8", newline="\n")
    return directory


def run_benchmark(conversations: int, messages: int, repetitions: int) -> dict[str, Any]:
    source_before = _source_reference()
    sys.path.insert(0, str(REPOSITORY / "src"))
    # Import only after the source snapshot is recorded. A changed snapshot at
    # exit invalidates attribution and is reported explicitly for a fresh run.
    from keepmorrow.catalog.model import CatalogLimits, validate_collection
    from keepmorrow.catalog.query import search_catalog
    from keepmorrow.catalog.service import import_exports, load_collection, recover_selection

    stage_samples: dict[str, list[dict[str, float | int]]] = {
        name: [] for name in ("initial_import", "extend_import", "verified_catalog_search", "selected_recovery")
    }
    wide_results: list[dict[str, Any]] = []
    observed_summaries: list[dict[str, Any]] = []
    manifest_digests: list[str] = []
    binary_checks = 0
    with tempfile.TemporaryDirectory(prefix="keepmorrow-collection-benchmark-") as temporary:
        root = Path(temporary).resolve()
        first, second, source_zip, workload = _write_corpus(root, conversations, messages)
        expected_binary = {
            (f"{index:06d}", path): _hash_file(directory / path)
            for index, directory in ((1, first), (2, second))
            for path in ("assets/evidence.bin", "assets/pixel.png")
        }
        for repetition in range(repetitions):
            initial, extended, recovered = (root / f"{name}-{repetition}"
                                             for name in ("initial", "extended", "recovered"))
            _, sample = _measure(lambda: import_exports([first], initial, account_namespace=NAMESPACE))
            stage_samples["initial_import"].append(sample)
            initial_manifest = _hash_file(initial / "manifest.json")
            result, sample = _measure(lambda: import_exports([source_zip], extended,
                                                            account_namespace=NAMESPACE, previous=initial))
            stage_samples["extend_import"].append(sample)
            if initial_manifest != _hash_file(initial / "manifest.json"):
                raise RuntimeError("Extending a generation changed its parent manifest.")
            for field, expected in workload["expected_summary"].items():
                if result.summary[field] != expected:
                    raise RuntimeError(f"The benchmark did not satisfy its expected {field}.")
            observed_summaries.append(result.summary)

            def query_checked() -> Any:
                collection = load_collection(extended)
                result = search_catalog(collection.document, "benchmark-search-marker", limit=20)
                if not result["items"]:
                    raise RuntimeError("The benchmark search did not find its known marker.")
                return collection

            collection, sample = _measure(query_checked)
            stage_samples["verified_catalog_search"].append(sample)
            binary_checks += _check_binary_bytes(collection, expected_binary)
            selected = next(item for item in collection.document["conversations"]
                            if item["source_id"] == "conversation-000000")
            _, sample = _measure(lambda: recover_selection(
                extended, recovered, conversation_keys=[selected["conversation_key"]]
            ))
            stage_samples["selected_recovery"].append(sample)
            restored = load_collection(recovered)
            binary_checks += _check_binary_bytes(restored, expected_binary)
            if (len(restored.document["conversations"]) != 1
                    or any("conversations" in Path(record.path).name or record.path.endswith("original.zip")
                           for record in restored.manifest.files)):
                raise RuntimeError("The selected recovery retained material outside its intended scope.")
            manifest_digests.append(_hash_file(extended / "manifest.json"))
        if len(set(manifest_digests)) != 1:
            raise RuntimeError("Equivalent benchmark inputs produced different archive manifests.")

        for width in WIDE_BRANCH_WIDTHS:
            source = _write_wide_export(root, width)
            archive = root / f"wide-archive-{width}"
            import_exports([source], archive, account_namespace=NAMESPACE)
            collection = load_collection(archive)
            samples = []
            for _ in range(repetitions):
                _, sample = _measure(lambda: validate_collection(collection.document, collection.manifest, CatalogLimits()))
                samples.append(sample)
            wide_results.append({"children_per_hub": width, "graph_nodes": width + 2,
                                 "samples": samples, "statistics": _statistics(samples)})
    source_after = _source_reference()
    stable_source = source_before == source_after
    width_ratio = wide_results[1]["children_per_hub"] / wide_results[0]["children_per_hub"]
    duration_ratio = (wide_results[1]["statistics"]["median_seconds"]
                      / wide_results[0]["statistics"]["median_seconds"])
    return {
        "format": "lpx-keepmorrow.collection-benchmark", "version": 1,
        "measured_at_utc": datetime.now(UTC).isoformat(), "environment": _environment(),
        "source_before": source_before, "source_after": source_after,
        "source_unchanged_during_run": stable_source,
        "source_attribution": "Current worktree file digests; no commit equivalence is asserted.",
        "workload": {**workload, "repetitions": repetitions},
        "stages": {name: {"samples": samples, "statistics": _statistics(samples)}
                   for name, samples in stage_samples.items()},
        "validation": {
            "expected_summary_matched_every_repetition": True,
            "exact_binary_hash_checks": binary_checks,
            "selected_recovery_conversation_count": 1,
            "selected_recovery_excludes_whole_source_json_and_zip": True,
            "parent_manifest_unchanged": True,
            "deterministic_manifest_across_repetitions": True,
            "final_generation_manifest_sha256": manifest_digests[0],
            "observed_summaries": observed_summaries,
        },
        "wide_branch_validation": {
            "operation": "validate_collection over already parsed, verified catalogs; excludes import and file verification",
            "results": wide_results, "input_width_ratio": width_ratio,
            "observed_median_time_ratio": duration_ratio,
            "interpretation": "A diagnostic size comparison, not a timing assertion or proof of asymptotic behavior.",
        },
        "methodology": [
            "Wall-clock timing includes tracemalloc overhead; gc.collect runs before each timed operation.",
            "Python-traced allocation peaks are not process RSS and exclude OS caches and some native allocations.",
            "Fixture generation, ZIP creation, and supplemental exact binary hash checks are outside timed regions.",
            "Filesystem caches are not flushed; generation, earlier stages, and repeated reads warm the cache.",
            "Initial import preserves one directory; extension preserves a second ZIP and copies prior captured payload into a new immutable generation.",
            "Verified catalog search includes full archive byte verification through load_collection before literal text search.",
            "Selected recovery includes the service's input and output verification; supplemental checks run afterward.",
            "The ZIP is deliberately compressible synthetic data; its compression ratio is not representative of arbitrary media.",
            "Three modest repetitions support medians and observed ranges, not percentile latency claims.",
            "No earlier semantic-collection baseline exists; no comparative speed or production capacity claim is made.",
            "If source_unchanged_during_run is false or implementation source changes later, rerun before attributing these results to that source.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--conversations", type=positive_int, default=100)
    parser.add_argument("--messages", type=positive_int, default=12)
    parser.add_argument("--repetitions", type=positive_int, default=3)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.conversations * (args.messages + 3) > 100_000:
        parser.error("The generated source would exceed the default import node budget.")
    document = run_benchmark(args.conversations, args.messages, args.repetitions)
    document["command"] = (
        f"PYTHONPATH=src python benchmarks/benchmark_collection.py --conversations {args.conversations} "
        f"--messages {args.messages} --repetitions {args.repetitions}"
        + (f" --output {args.output.as_posix()}" if args.output else "")
    )
    encoded = json.dumps(document, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    if args.output is None:
        print(encoded, end="")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8", newline="\n")
        print(json.dumps({
            "report_path": args.output.as_posix(),
            "source_unchanged_during_run": document["source_unchanged_during_run"],
            "median_seconds": {name: value["statistics"]["median_seconds"] for name, value in document["stages"].items()},
            "wide_branch_median_time_ratio": document["wide_branch_validation"]["observed_median_time_ratio"],
        }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
