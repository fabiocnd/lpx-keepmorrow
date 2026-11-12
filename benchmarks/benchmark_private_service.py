"""Measure the private service with isolated, deterministic synthetic inputs.

The parent launches one fresh interpreter. The child runs the same workflow
three times against one service instance, preserving earlier outputs so that
warm runs include the growing metadata ledger. Browser, OAuth, HTTP transport,
and genuine human acceptance are outside this experiment.

Copyright 2026 Lopix Neural Inc. All rights reserved.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable
from datetime import UTC, datetime
import hashlib
import json
import os
from pathlib import Path
import platform
import sqlite3
import stat
import statistics
import subprocess
import sys
import tempfile
import threading
import time
from typing import Any
import uuid
import zipfile

REPOSITORY = Path(__file__).resolve().parents[1]
GENERATOR_VERSION = 1
CHUNK_BYTES = 1024**2
DISK_SAMPLE_INTERVAL_SECONDS = 0.05
STATUS_POLL_INTERVAL_SECONDS = 0.01
TERMINAL_STATES = frozenset({"completed", "partial", "failed", "cancelled", "interrupted", "expired"})
DISK_CATEGORIES = ("fixtures", "downloads", "outputs", "uploads", "scratch", "control_metadata", "other")


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while block := source.read(CHUNK_BYTES):
            digest.update(block)
    return digest.hexdigest()


def _json_digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _source_reference() -> dict[str, Any]:
    paths = sorted((REPOSITORY / "src").rglob("*.py")) + [Path(__file__).resolve()]
    files = {path.relative_to(REPOSITORY).as_posix(): _hash_file(path) for path in paths}
    return {"kind": "worktree_file_sha256", "aggregate_sha256": _json_digest(files), "files": files}


def _optional_text(path: str, maximum: int = 8192) -> str | None:
    try:
        with Path(path).open("r", encoding="utf-8") as source:
            return source.read(maximum).strip()
    except (OSError, UnicodeError):
        return None


def _environment(root: Path) -> dict[str, Any]:
    cpu_model = platform.processor() or None
    cpu_info = _optional_text("/proc/cpuinfo", 65536)
    if cpu_info:
        cpu_model = next((line.split(":", 1)[1].strip() for line in cpu_info.splitlines()
                          if line.startswith("model name") and ":" in line), cpu_model)
    filesystem = os.statvfs(root) if hasattr(os, "statvfs") else None
    return {
        "python_version": platform.python_version(), "python_implementation": platform.python_implementation(),
        "python_full_version": sys.version, "platform": platform.platform(), "architecture": platform.machine(),
        "cpu_model": cpu_model, "logical_cpus_reported_by_os": os.cpu_count(),
        "linux_cgroup_cpu_max": _optional_text("/sys/fs/cgroup/cpu.max"),
        "linux_cgroup_memory_max": _optional_text("/sys/fs/cgroup/memory.max"),
        "sqlite_runtime_version": sqlite3.sqlite_version,
        "storage": {
            "location": "Host default TemporaryDirectory storage",
            "filesystem_block_bytes": filesystem.f_frsize if filesystem else None,
            "available_bytes_at_setup": filesystem.f_bavail * filesystem.f_frsize if filesystem else None,
            "medium": "not characterized", "cache_residency": "not controlled",
        },
    }


def _process_usage() -> dict[str, Any]:
    try:
        import resource
    except ImportError:
        return {"peak_rss_bytes": None, "reason": "resource.getrusage is unavailable on this platform"}
    usage = resource.getrusage(resource.RUSAGE_SELF)
    multiplier = 1 if sys.platform == "darwin" else 1024 if sys.platform.startswith("linux") else None
    return {
        "source": "resource.getrusage(resource.RUSAGE_SELF) in the isolated child",
        "peak_rss_raw": usage.ru_maxrss,
        "peak_rss_raw_unit": "bytes" if multiplier == 1 else "KiB" if multiplier == 1024 else "platform dependent",
        "peak_rss_bytes": usage.ru_maxrss * multiplier if multiplier else None,
        "user_cpu_seconds": usage.ru_utime, "system_cpu_seconds": usage.ru_stime,
        "scope": "Cumulative process high-water mark, including fixture generation, service, and measurement threads",
    }


def _record(index: int, node_count: int) -> dict[str, Any]:
    mapping: dict[str, Any] = {
        "root": {"id": "root", "parent": None, "children": ["node-001"], "message": None}
    }
    branched = index % 5 == 0 and node_count >= 7
    last = node_count - 1
    for offset in range(1, node_count):
        node_id = f"node-{offset:03d}"
        parent = "root" if offset == 1 else f"node-{offset - 1:03d}"
        if branched and offset == last:
            parent = "node-003"
        children = [f"node-{offset + 1:03d}"] if offset < last else []
        if branched and offset == last - 1:
            children = []
        if branched and offset == 3:
            children.append(f"node-{last:03d}")
        message: dict[str, Any] = {
            "id": f"message-{offset:03d}", "author": {"role": "user" if offset % 2 else "assistant"},
            "content": {"content_type": "text", "parts": [
                f"Synthetic conversation {index:06d}, node {offset:03d}. Preserve supplied bytes."
                + (" benchmark-search-marker" if offset == last else "")
            ]},
        }
        if offset == 1:
            message["metadata"] = {"attachments": [{
                "id": "synthetic-binary", "relative_path": "assets/evidence.bin",
                "name": "evidence.bin", "mime_type": "application/octet-stream",
            }]}
        mapping[node_id] = {"id": node_id, "parent": parent, "children": children, "message": message}
    return {
        "id": f"conversation-{index:06d}", "title": f"Synthetic preservation topic {index:06d}",
        "project_id": f"project-{index % 3 + 1}", "mapping": mapping,
        "current_node": f"node-{last - 1 if branched else last:03d}",
        "fixture_metadata": {"generator_version": GENERATOR_VERSION},
    }


def _write_fixture(root: Path, conversations: int, nodes: int, binary_mib: int) -> tuple[Path, dict[str, Any]]:
    root.mkdir(mode=0o700)
    source = root / "source"
    (source / "assets").mkdir(parents=True, mode=0o700)
    records = [_record(index, nodes) for index in range(conversations)]
    (source / "conversations.json").write_bytes(
        json.dumps(records, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    )
    # Repeated byte values make the fixture reproducible. ZIP_STORED keeps this
    # workload from depending on its intentionally simple compression ratio.
    block = bytes(range(256)) * 4096
    with (source / "assets/evidence.bin").open("xb") as output:
        for _ in range(binary_mib):
            output.write(block)
    inventory = {
        path.relative_to(source).as_posix(): {"size_bytes": path.stat().st_size, "sha256": _hash_file(path)}
        for path in sorted(source.rglob("*")) if path.is_file()
    }
    container = root / "input.zip"
    with zipfile.ZipFile(container, "x", allowZip64=False) as archive:
        for name in sorted(inventory):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_STORED
            info.external_attr = (stat.S_IFREG | 0o600) << 16
            info.create_system = 3
            with (source / name).open("rb") as reader, archive.open(info, "w") as writer:
                while chunk := reader.read(CHUNK_BYTES):
                    writer.write(chunk)
    return container, {
        "generator_version": GENERATOR_VERSION, "seed": "deterministic; no random generator",
        "conversations": conversations, "graph_nodes_per_conversation": nodes,
        "message_nodes_per_conversation": nodes - 1, "structural_roots_per_conversation": 1,
        "graph_nodes_total": conversations * nodes,
        "branched_conversations": (conversations + 4) // 5 if nodes >= 7 else 0,
        "captures_per_run": 1, "revisions_per_conversation": 1, "projects": min(conversations, 3),
        "binary_payload_bytes": binary_mib * CHUNK_BYTES, "artifact_references": conversations,
        "distinct_binary_files": 1, "source_file_count": len(inventory), "maximum_source_path_depth": 2,
        "source_files": inventory, "expanded_source_bytes": sum(value["size_bytes"] for value in inventory.values()),
        "submitted_zip_bytes": container.stat().st_size, "submitted_zip_sha256": _hash_file(container),
        "compression": "ZIP_STORED; non-ZIP64", "recovery_conversations": min(10, conversations),
    }


def _disk_category(relative: Path) -> str:
    parts = relative.parts
    if parts[0] in {"fixtures", "downloads"}:
        return parts[0]
    if parts[0] == "state":
        return parts[1] if len(parts) > 1 and parts[1] in {"outputs", "uploads", "scratch"} else "control_metadata"
    return "other"


def _disk_snapshot(root: Path) -> dict[str, Any]:
    totals = {name: {"logical_bytes": 0, "allocated_bytes": 0, "files": 0} for name in DISK_CATEGORIES}
    pending = [root]
    disappeared, errors, symlinks = 0, 0, 0
    while pending:
        directory = pending.pop()
        try:
            with os.scandir(directory) as entries:
                for entry in entries:
                    try:
                        status = entry.stat(follow_symlinks=False)
                    except FileNotFoundError:
                        disappeared += 1
                        continue
                    if stat.S_ISDIR(status.st_mode):
                        pending.append(Path(entry.path))
                    elif stat.S_ISREG(status.st_mode):
                        category = totals[_disk_category(Path(entry.path).relative_to(root))]
                        category["logical_bytes"] += status.st_size
                        category["allocated_bytes"] += getattr(status, "st_blocks", 0) * 512
                        category["files"] += 1
                    elif stat.S_ISLNK(status.st_mode):
                        symlinks += 1
        except FileNotFoundError:
            disappeared += 1
        except OSError:
            errors += 1
    return {
        "logical_bytes": sum(item["logical_bytes"] for item in totals.values()),
        "allocated_bytes": sum(item["allocated_bytes"] for item in totals.values()),
        "files": sum(item["files"] for item in totals.values()), "categories": totals,
        "disappeared_during_scan": disappeared, "scan_errors": errors, "symlinks": symlinks,
    }


class DiskSampler:
    """Sample owned regular files without reading their contents or following links.

    Concurrent publication can move a file between two visited directories, so
    an observation is not an atomic inventory. Sampled maxima are observations,
    not a proven peak or an allocation budget.
    """

    def __init__(self, root: Path) -> None:
        self.root = root
        self.stop = threading.Event()
        self.samples: list[dict[str, Any]] = []
        self.started = time.perf_counter()
        self.scan_seconds = 0.0
        self.thread = threading.Thread(target=self._run, name="benchmark-disk-sampler", daemon=True)

    def _sample(self) -> None:
        started = time.perf_counter()
        snapshot = _disk_snapshot(self.root)
        self.scan_seconds += time.perf_counter() - started
        snapshot["offset_seconds"] = time.perf_counter() - self.started
        self.samples.append(snapshot)

    def _run(self) -> None:
        while not self.stop.wait(DISK_SAMPLE_INTERVAL_SECONDS):
            self._sample()

    def __enter__(self) -> DiskSampler:
        self._sample()
        self.thread.start()
        return self

    def __exit__(self, *unused: object) -> None:
        self.stop.set()
        self.thread.join()
        self._sample()

    def report(self) -> dict[str, Any]:
        return {
            "before": self.samples[0], "after": self.samples[-1], "sample_count": len(self.samples),
            "peak_observed_logical_bytes": max(item["logical_bytes"] for item in self.samples),
            "peak_observed_allocated_bytes": max(item["allocated_bytes"] for item in self.samples),
            "peak_observed_by_category": {
                name: {field: max(item["categories"][name][field] for item in self.samples)
                       for field in ("logical_bytes", "allocated_bytes", "files")}
                for name in DISK_CATEGORIES
            },
            "scan_seconds": self.scan_seconds,
            "disappeared_during_scan": sum(item["disappeared_during_scan"] for item in self.samples),
            "scan_errors": sum(item["scan_errors"] for item in self.samples),
            "profile": [{"offset_seconds": item["offset_seconds"], "logical_bytes": item["logical_bytes"],
                         "scratch_logical_bytes": item["categories"]["scratch"]["logical_bytes"]}
                        for item in self.samples],
        }


def _measure(root: Path, execute: Callable[[], Any]) -> tuple[Any, dict[str, Any]]:
    with DiskSampler(root) as sampler:
        started = time.perf_counter()
        result = execute()
        seconds = time.perf_counter() - started
    return result, {"seconds": seconds, "disk": sampler.report()}


def _timing_summary(samples: list[float]) -> dict[str, float | int | None]:
    return {
        "sample_count": len(samples), "minimum_seconds": min(samples) if samples else None,
        "median_seconds": statistics.median(samples) if samples else None,
        "maximum_seconds": max(samples) if samples else None,
    }


class Workflow:
    def __init__(self, service: Any, principal: Any, root: Path, timeout_seconds: float) -> None:
        self.service, self.principal, self.root = service, principal, root
        self.timeout_seconds = timeout_seconds

    def accept(self, resource_id: str, generation: str, actions: list[str]) -> None:
        # These receipts exercise storage and authorization costs only. No
        # browser session or authenticated human gesture exists in this driver.
        grant = self.service.prepare_consent(
            self.principal, resource_id=resource_id, generation=generation, actions=actions,
        )
        self.service.access.accept_grant(
            self.principal, grant_id=grant.grant_id, expected_grant_version=grant.grant_version,
            policies=self.service.policies, actions=actions,
            interaction_id="synthetic_benchmark_" + uuid.uuid4().hex,
        )

    def execute_plan(self, resource_id: str, generation: str, parameters: Any) -> tuple[dict[str, Any], dict[str, Any]]:
        control_samples: list[dict[str, Any]] = []

        def execute() -> dict[str, Any]:
            plan = self.service.prepare(self.principal, resource_id=resource_id, generation=generation, parameters=parameters)
            self.service.operations.record_human_review(
                self.principal.principal_id, plan.plan_id, parameter_digest=plan.parameter_digest,
                interaction_id="synthetic_benchmark_" + uuid.uuid4().hex,
            )
            started = self.service.start(self.principal, plan.plan_id, "benchmark_" + uuid.uuid4().hex)
            deadline = time.monotonic() + self.timeout_seconds
            while time.monotonic() < deadline:
                before = time.perf_counter()
                snapshot = self.service.status(self.principal, started["operation_id"])
                status_seconds = time.perf_counter() - before
                if snapshot["state"] in TERMINAL_STATES:
                    if snapshot["state"] not in {"completed", "partial"} or snapshot["result"] is None:
                        raise RuntimeError(f"Synthetic {snapshot['kind']} ended in {snapshot['state']}: {snapshot['error_code']}")
                    return snapshot
                before = time.perf_counter()
                listing = self.service.list_collections(self.principal, limit=20)
                control_samples.append({
                    "observed_state": snapshot["state"], "status_seconds": status_seconds,
                    "list_collections_seconds": time.perf_counter() - before,
                    "collection_refs_returned": len(listing["items"]),
                })
                time.sleep(STATUS_POLL_INTERVAL_SECONDS)
            raise RuntimeError("The synthetic service operation exceeded its measurement deadline.")

        snapshot, measured = _measure(self.root, execute)
        active = [sample for sample in control_samples if sample["observed_state"] in {"running", "verifying", "cancel_requested"}]
        measured.update({
            "scope": "prepare, synthetic review persistence, enqueue, execution, integrity checks, and terminal-status polling",
            "state": snapshot["state"], "result": snapshot["result"],
            "control_plane": {
                "samples": control_samples,
                "status_nonterminal": _timing_summary([sample["status_seconds"] for sample in control_samples]),
                "list_collections_nonterminal": _timing_summary([sample["list_collections_seconds"] for sample in control_samples]),
                "status_observed_active": _timing_summary([sample["status_seconds"] for sample in active]),
                "list_collections_observed_active": _timing_summary([sample["list_collections_seconds"] for sample in active]),
            },
        })
        return snapshot, measured

    def content(self, execute: Callable[[], Any]) -> tuple[Any, dict[str, Any]]:
        from keepmorrow.operations import OperationBusy

        retries = 0

        def admitted() -> Any:
            nonlocal retries
            deadline = time.monotonic() + self.timeout_seconds
            while True:
                try:
                    return execute()
                except OperationBusy:
                    if time.monotonic() >= deadline:
                        raise
                    retries += 1
                    time.sleep(STATUS_POLL_INTERVAL_SECONDS)

        result, measured = _measure(self.root, admitted)
        measured["content_admission_retries"] = retries
        return result, measured

    def run(self, ordinal: int, input_path: Path, workload: dict[str, Any]) -> dict[str, Any]:
        from keepmorrow.application.service import workspace_id
        from keepmorrow.catalog.query import browse_catalog, read_revision, search_catalog
        from keepmorrow.operations import ImportParameters, PackageParameters, RecoveryParameters, UnpackParameters

        started = time.perf_counter()
        stages: dict[str, Any] = {}
        workspace = workspace_id(self.principal)
        _, stages["synthetic_workspace_acceptance"] = _measure(
            self.root, lambda: self.accept(workspace, "workspace_v1", ["upload", "import", "unpack"]),
        )

        def upload(path: Path) -> dict[str, Any]:
            with path.open("rb") as source:
                return self.service.receive_upload(
                    self.principal, source, display_name=path.name, expected_size_bytes=path.stat().st_size,
                )

        receipt, stages["input_upload"] = _measure(self.root, lambda: upload(input_path))
        if receipt["sha256"] != workload["submitted_zip_sha256"] or receipt["size_bytes"] != workload["submitted_zip_bytes"]:
            raise RuntimeError("The synthetic upload changed the supplied byte identity.")
        imported, stages["import"] = self.execute_plan(
            workspace, "workspace_v1", ImportParameters(receipt["upload_id"], receipt["sha256"], "synthetic-service-benchmark"),
        )
        imported_id, imported_generation = imported["output_id"], imported["result"]["manifest_sha256"]
        _, stages["synthetic_collection_acceptance"] = _measure(
            self.root, lambda: self.accept(imported_id, imported_generation, ["browse", "search", "read", "recover"]),
        )

        def query(action: str, execute: Callable[[Any], dict[str, Any]]) -> dict[str, Any]:
            return self.service.query(self.principal, imported_id, imported_generation, action, execute)

        browsing, stages["browse_query"] = self.content(lambda: query("browse", lambda item: browse_catalog(item.document, limit=20)))
        selected = tuple(item["conversation_key"] for item in browsing["items"][:workload["recovery_conversations"]])
        if browsing["total"] != workload["conversations"] or len(selected) != workload["recovery_conversations"]:
            raise RuntimeError("The synthetic import did not expose its expected conversation scope.")
        searching, stages["search_query"] = self.content(
            lambda: query("search", lambda item: search_catalog(item.document, "benchmark-search-marker", limit=20)),
        )
        reading, stages["read_query"] = self.content(
            lambda: query("read", lambda item: read_revision(item.document, selected[0], limit=20)),
        )
        if reading["total_nodes"] != workload["graph_nodes_per_conversation"] or len(searching["items"]) != min(20, workload["conversations"]):
            raise RuntimeError("The synthetic query did not return its expected bounded graph or search page.")
        recovered, stages["recover"] = self.execute_plan(imported_id, imported_generation, RecoveryParameters(selected))
        recovered_id, recovered_generation = recovered["output_id"], recovered["result"]["manifest_sha256"]
        _, stages["synthetic_recovery_acceptance"] = _measure(
            self.root, lambda: self.accept(recovered_id, recovered_generation, ["package"]),
        )
        packaged, stages["package"] = self.execute_plan(recovered_id, recovered_generation, PackageParameters())
        package_id, package_generation = packaged["output_id"], packaged["result"]["manifest_sha256"]
        _, stages["synthetic_download_acceptance"] = _measure(
            self.root, lambda: self.accept(package_id, package_generation, ["download"]),
        )
        destination = self.root / "downloads" / f"recovery-{ordinal}.zip"

        def download() -> dict[str, Any]:
            digest, size = hashlib.sha256(), 0
            with self.service.download(self.principal, package_id, package_generation) as (source, expected):
                with destination.open("xb") as output:
                    while block := source.read(CHUNK_BYTES):
                        output.write(block)
                        digest.update(block)
                        size += len(block)
            if size != expected or digest.hexdigest() != packaged["result"]["artifact_sha256"]:
                raise RuntimeError("The downloaded synthetic package differs from its verified receipt.")
            return {"size_bytes": size, "sha256": digest.hexdigest()}

        downloaded, stages["download"] = self.content(download)
        stages["download"]["scope"] = "service authorization and full package revalidation, followed by local streaming copy and SHA-256"
        second_receipt, stages["recovery_upload"] = _measure(self.root, lambda: upload(destination))
        if second_receipt["sha256"] != downloaded["sha256"] or second_receipt["size_bytes"] != downloaded["size_bytes"]:
            raise RuntimeError("The recovery upload changed the verified package bytes.")
        unpacked, stages["unpack"] = self.execute_plan(
            workspace, "workspace_v1", UnpackParameters(second_receipt["upload_id"], second_receipt["sha256"]),
        )
        if unpacked["result"]["manifest_sha256"] != recovered_generation:
            raise RuntimeError("The unpacked collection changed its original manifest bytes.")
        unpacked_id = unpacked["output_id"]
        _, stages["synthetic_validation_acceptance"] = _measure(
            self.root, lambda: self.accept(unpacked_id, recovered_generation, ["verify"]),
        )

        def validate(collection: Any) -> dict[str, Any]:
            identities = {item["conversation_key"] for item in collection.document["conversations"]}
            if identities != set(selected):
                raise RuntimeError("The synthetic recovery changed its explicit conversation selection.")
            binaries = []
            for capture in collection.document["captures"]:
                for record in capture["files"]:
                    if record["path"] == "assets/evidence.bin":
                        target = collection.root / "payload/captures" / capture["storage_id"] / "source" / record["path"]
                        binaries.append(_hash_file(target))
            if binaries != [workload["source_files"]["assets/evidence.bin"]["sha256"]]:
                raise RuntimeError("The recovered synthetic binary did not preserve its exact supplied bytes.")
            original = self.service.resources.resolve(self.principal, imported_id, imported_generation).path
            if _hash_file(original / "payload/captures/000001/original.zip") != workload["submitted_zip_sha256"]:
                raise RuntimeError("The original submitted ZIP did not remain byte-identical.")
            return {
                "selected_conversation_count": len(identities), "binary_files_checked": len(binaries),
                "binary_sha256": binaries[0], "original_zip_preserved": True, "manifest_bytes_preserved": True,
            }

        validation, stages["roundtrip_validation"] = self.content(
            lambda: self.service.query(self.principal, unpacked_id, recovered_generation, "verify", validate),
        )
        return {
            "ordinal": ordinal, "phase": "first_pass_in_fresh_process" if ordinal == 1 else "subsequent_pass_in_same_process",
            "total_seconds": time.perf_counter() - started, "stages": stages,
            "output": {"download": downloaded, "roundtrip_validation": validation,
                       "browse_items": len(browsing["items"]), "search_items": len(searching["items"]),
                       "read_nodes": len(reading["nodes"]), "read_next_offset": reading["next_offset"]},
            "process_usage_cumulative": _process_usage(),
        }


def _child(arguments: argparse.Namespace) -> dict[str, Any]:
    source_before = _source_reference()
    sys.path.insert(0, str(REPOSITORY / "src"))
    imported_at = time.perf_counter()
    from keepmorrow.access import Principal
    from keepmorrow.application.configuration import ServiceConfiguration
    from keepmorrow.application.service import PreservationService
    runtime_import_seconds = time.perf_counter() - imported_at
    policies = {name: _hash_file(REPOSITORY / "legal" / name) for name in ("terms-of-use.md", "privacy-notice.md")}
    with tempfile.TemporaryDirectory(prefix="keepmorrow-service-benchmark-") as temporary:
        root = Path(temporary).resolve()
        environment = _environment(root)
        fixture_started = time.perf_counter()
        input_path, workload = _write_fixture(root / "fixtures", arguments.conversations, arguments.nodes, arguments.binary_mib)
        fixture_seconds = time.perf_counter() - fixture_started
        (root / "state").mkdir(mode=0o700)
        (root / "downloads").mkdir(mode=0o700)
        principal = Principal("urn:lpx-keepmorrow:local-operator", "synthetic-benchmark")
        configuration = ServiceConfiguration(root / "state", REPOSITORY / "legal", "http://127.0.0.1:8765", (principal,))
        service_started = time.perf_counter()
        service = PreservationService(configuration)
        service.start_worker()
        service_seconds = time.perf_counter() - service_started
        runs: list[dict[str, Any]] = []
        try:
            workflow = Workflow(service, principal, root, arguments.timeout_seconds)
            for ordinal in range(1, arguments.repetitions + 1):
                runs.append(workflow.run(ordinal, input_path, workload))
        finally:
            service.stop_worker()
        final_disk = _disk_snapshot(root)
        policy_identity = service.policies.as_dict()
    source_after = _source_reference()
    stage_names = list(runs[0]["stages"])
    return {
        "schema_version": 1, "benchmark": "private_service_synthetic", "recorded_at_utc": datetime.now(UTC).isoformat(),
        "source": source_before, "source_after_aggregate_sha256": source_after["aggregate_sha256"],
        "source_unchanged_during_run": source_before == source_after,
        "policy_files_sha256": policies, "policy_identity": policy_identity, "environment": environment,
        "workload": workload, "configuration": {
            "worker_count": 1, "content_io_slots": 1, "service_mode": "operator",
            "max_upload_bytes": configuration.max_upload_bytes, "max_storage_bytes": configuration.max_storage_bytes,
            "retention_seconds": configuration.retention_seconds,
        },
        "conditions": {
            "fresh_processes": 1, "pipeline_repetitions": arguments.repetitions,
            "service_instances": 1, "outputs_and_uploads_retained_between_runs": True,
            "filesystem_cache": "Not controlled; the fixture is generated and hashed immediately before the first run",
            "python_hash_seed": os.environ.get("PYTHONHASHSEED", "not set; interpreter default"),
            "background_load": "Not controlled on the shared host", "tracemalloc_enabled": False,
            "human_interactions": "Synthetic benchmark receipts and plan reviews; not evidence of human acceptance",
            "transport": "Direct application service calls; no HTTP, OAuth provider, browser, ChatGPT host, or remote network",
            "disk_sampling_interval_seconds": DISK_SAMPLE_INTERVAL_SECONDS,
            "status_poll_interval_seconds": STATUS_POLL_INTERVAL_SECONDS,
            "timing": "perf_counter wall time; stage timing includes concurrent sampler contention and normal validation",
        },
        "startup": {"application_import_seconds": runtime_import_seconds,
                    "fixture_generation_and_hashing_seconds": fixture_seconds,
                    "service_initialization_and_worker_start_seconds": service_seconds},
        "runs": runs,
        "summary": {
            "first_pass_seconds": runs[0]["total_seconds"],
            "subsequent_passes": _timing_summary([run["total_seconds"] for run in runs[1:]]),
            "stages_all_passes": {name: _timing_summary([run["stages"][name]["seconds"] for run in runs]) for name in stage_names},
        },
        "final_disk_before_temporary_root_cleanup": final_disk, "process_usage": _process_usage(),
        "limitations": [
            "A fresh Python process does not establish a cold filesystem, CPU cache, or storage device.",
            "The first-pass stage timings exclude separately recorded runtime imports, fixture generation, and service setup.",
            "Fixture generation occurs in the measured child and can warm its allocator before the first service operation.",
            "Subsequent passes reuse one service and retain earlier outputs; they are not independent cold samples.",
            "Control-plane observations are in-process calls classified by the preceding status; state can change during a call.",
            "Disk scans are non-atomic and can miss transient peaks or count a concurrently renamed file twice.",
            "Disk figures count regular-file logical size and st_blocks allocation; directory and filesystem metadata are excluded.",
            "Per-category disk maxima can occur at different times and must not be summed as a simultaneous total.",
            "Peak RSS is the cumulative child-process high-water mark, not an isolated allocation measurement for each stage.",
            "These bounded synthetic measurements do not establish load capacity, production reliability, or general speed improvements.",
        ],
    }


def _bounded_int(minimum: int, maximum: int) -> Callable[[str], int]:
    def parse(value: str) -> int:
        parsed = int(value)
        if not minimum <= parsed <= maximum:
            raise argparse.ArgumentTypeError(f"The value must be between {minimum} and {maximum}.")
        return parsed
    return parse


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--conversations", type=_bounded_int(1, 1000), default=250)
    parser.add_argument("--nodes", type=_bounded_int(2, 64), default=12, help="Total graph nodes, including one structural root")
    parser.add_argument("--binary-mib", type=_bounded_int(1, 32), default=8)
    parser.add_argument("--repetitions", type=_bounded_int(1, 4), default=3)
    parser.add_argument("--timeout-seconds", type=_bounded_int(10, 300), default=120)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--child", action="store_true", help=argparse.SUPPRESS)
    arguments = parser.parse_args()
    if arguments.child:
        report = _child(arguments)
    else:
        command = [sys.executable, str(Path(__file__).resolve()), "--child", "--conversations", str(arguments.conversations),
                   "--nodes", str(arguments.nodes), "--binary-mib", str(arguments.binary_mib),
                   "--repetitions", str(arguments.repetitions), "--timeout-seconds", str(arguments.timeout_seconds)]
        started = time.perf_counter()
        child = subprocess.run(command, cwd=REPOSITORY, capture_output=True, text=True, check=False,
                               timeout=arguments.repetitions * arguments.timeout_seconds * 6 + 60)
        elapsed = time.perf_counter() - started
        if child.returncode:
            raise SystemExit(child.stderr or f"The benchmark child exited with status {child.returncode}.")
        report = json.loads(child.stdout)
        report["parent_observed_child_wall_seconds"] = elapsed
        report["command"] = [sys.executable, "benchmarks/benchmark_private_service.py",
                             "--conversations", str(arguments.conversations), "--nodes", str(arguments.nodes),
                             "--binary-mib", str(arguments.binary_mib), "--repetitions", str(arguments.repetitions),
                             "--timeout-seconds", str(arguments.timeout_seconds)]
        if arguments.output:
            report["command"].extend(["--output", arguments.output.as_posix()])
    encoded = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if arguments.output and not arguments.child:
        if not report["source_unchanged_during_run"]:
            raise SystemExit("Source files changed during measurement; no reference result was written.")
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(encoded, encoding="utf-8", newline="\n")
        print(json.dumps({"output": str(arguments.output), "source_sha256": report["source"]["aggregate_sha256"],
                          "first_pass_seconds": report["summary"]["first_pass_seconds"],
                          "subsequent_passes": report["summary"]["subsequent_passes"],
                          "peak_rss_bytes": report["process_usage"]["peak_rss_bytes"]}, indent=2))
    else:
        print(encoded, end="")


if __name__ == "__main__":
    main()
