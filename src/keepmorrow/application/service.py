"""Authorize, coordinate, and reconcile the private preservation service.

Copyright 2026 Lopix Neural Inc. All rights reserved.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager, nullcontext
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import tempfile
import threading
import time
from typing import Any, BinaryIO

from ..access import AccessDenied, AccessStore, Grant, Principal
from ..archive.filesystem import open_regular, publish_directory, safe_directory
from ..archive.model import ArchiveError, Limits
from ..catalog.model import effective_associations
from ..catalog.service import (
    LoadedCollection, associate_conversation, import_exports, load_collection, recover_selection,
)
from ..control import execution_scope, temporary_parent
from ..operations import (
    AssociationParameters, AuthorizationScope, ImportParameters, OperationAttempt,
    OperationBusy, OperationLimits, OperationPlan, OperationSnapshot, OperationStore,
    OperationParameters, OperationWorker, PackageParameters, RecoveryParameters, UnpackParameters, VerifiedResult,
)
from ..persistence import SQLiteDatabase
from ..transfers import PackageLimits, UploadLimits, UploadStore, pack_collection, unpack_collection
from .configuration import OPERATION_RESERVATION_BYTES, Resource, ServiceConfiguration
from .resources import ResourceRegistry
from .staging import OperationWorkspaces

COLLECTION_ACTIONS = frozenset({"browse", "search", "read", "verify", "recover", "associate", "package", "import"})
WORKSPACE_ACTIONS = frozenset({"upload", "import", "unpack"})
ARCHIVE_LIMITS = Limits(max_total_bytes=512 * 1024**2, max_file_bytes=512 * 1024**2)


def workspace_id(principal: Principal) -> str:
    return "workspace_" + principal.principal_id.removeprefix("principal_")


def manifest_digest(path: Path) -> str:
    with open_regular(path / "manifest.json") as source:
        data = source.read(ARCHIVE_LIMITS.max_manifest_bytes + 1)
    if len(data) > ARCHIVE_LIMITS.max_manifest_bytes:
        raise ArchiveError("The manifest exceeds the configured byte limit.")
    return hashlib.sha256(data).hexdigest()


def _file_digest(path: Path, maximum: int) -> tuple[str, int]:
    digest, size = hashlib.sha256(), 0
    with open_regular(path) as source:
        before = os.fstat(source.fileno())
        while block := source.read(1024**2):
            size += len(block)
            if size > maximum:
                raise ArchiveError("The artifact exceeds its byte limit.")
            digest.update(block)
        after = os.fstat(source.fileno())
    if (size != before.st_size or before.st_size != after.st_size
            or before.st_mtime_ns != after.st_mtime_ns or before.st_ctime_ns != after.st_ctime_ns):
        raise ArchiveError("The artifact changed during verification.")
    return digest.hexdigest(), size


def _coverage(collection: LoadedCollection) -> tuple[str, ...]:
    gaps: set[str] = set()
    if collection.document["scope"] != "supplied_exports":
        gaps.add("selection_omissions")
    if any(item["state"] == "association_unknown" for item in effective_associations(collection.document).values()):
        gaps.add("association_unknown")
    for capture in collection.document["captures"]:
        if capture["status"] != "complete":
            gaps.add("unsupported_records")
    for conversation in collection.document["conversations"]:
        # Association is summarized from explicit source evidence or decisions;
        # an unresolved relationship is never promoted to a confirmed project.
        for revision in conversation["revisions"]:
            for occurrence in revision["occurrences"]:
                if any(item["status"] != "stored" for item in occurrence["artifacts"]):
                    gaps.add("unresolved_artifacts")
    return tuple(sorted(gaps))


class PreservationService:
    """One metadata store, one worker, and one bounded content-I/O admission slot.

    Paths originate only from configuration or server-generated output IDs.
    Source account labels remain provenance; they never determine ownership.
    Content admission and result delivery both recheck the exact grant.
    """

    def __init__(self, configuration: ServiceConfiguration) -> None:
        self.configuration = configuration
        self.root = safe_directory(configuration.state_directory)
        for name in ("outputs", "uploads", "scratch"):
            (self.root / name).mkdir(mode=0o700, exist_ok=True)
            safe_directory(self.root / name)
        self.database = SQLiteDatabase(self.root / "control.sqlite3")
        self.policies, self.policy_documents = configuration.policies()
        self.access = AccessStore(self.database, self.policies)
        self.resources = ResourceRegistry(self.database, self.root / "outputs", configuration.resources)
        self.operations = OperationStore(self.database, limits=OperationLimits(
            max_reserved_bytes=configuration.max_storage_bytes,
            max_operation_reserved_bytes=OPERATION_RESERVATION_BYTES,
        ))
        self.workspaces = OperationWorkspaces(self.database, self.root / "scratch", self.resources.output_root)
        self.uploads = UploadStore(self.root / "uploads", limits=UploadLimits(
            max_upload_bytes=configuration.max_upload_bytes,
            max_owner_bytes=2 * configuration.max_upload_bytes,
            max_total_bytes=configuration.upload_pool_bytes,
            lifetime_seconds=min(3600, configuration.retention_seconds),
        ))
        self._io = threading.Lock()
        self.worker = OperationWorker(self.operations, self._execute, self._inspect_interrupted,
                                      classify_failure=self._failure_code, startup=self._startup)
        self._principals = {principal.principal_id: principal for principal in configuration.principals}

    @staticmethod
    def _failure_code(error: BaseException) -> str:
        if isinstance(error, AccessDenied):
            return "authorization_denied"
        if isinstance(error, ArchiveError):
            return "integrity_failed"
        if isinstance(error, OSError):
            return "input_unavailable"
        return "execution_failed"

    def principal(self, principal_id: str) -> Principal:
        try:
            return self._principals[principal_id]
        except (KeyError, TypeError):
            raise AccessDenied() from None

    def start_worker(self) -> None:
        self.worker.start()
        self.maintenance()

    def stop_worker(self) -> bool:
        return self.worker.shutdown(timeout_seconds=5, cancel_active=True)

    def _startup(self) -> None:
        # OperationWorker invokes this only while holding the process-exclusive
        # lock and before any new executor can borrow an upload.
        self.workspaces.recover_interrupted()
        self.uploads.recover_interrupted()

    def maintenance(self) -> dict[str, int]:
        removed_uploads = self.uploads.cleanup_expired()
        removed_packages = 0
        if self._io.acquire(blocking=False):
            try:
                for item in self.resources.expired_packages():
                    path = self.resources.output_root / str(item["resource_id"])
                    if os.path.lexists(path):
                        safe_directory(path)
                        if (manifest_digest(path) != item["generation"]
                                or {child.name for child in path.iterdir()} != {"manifest.json", "package.zip"}):
                            continue
                        # Only service-owned, expired delivery wrappers qualify.
                        # Source archives and persistent collection generations
                        # are never selected by this retention sweep.
                        shutil.rmtree(path)
                    self.resources.mark_removed(str(item["resource_id"]), str(item["generation"]))
                    removed_packages += 1
            finally:
                self._io.release()
        return {"removed_uploads": removed_uploads, "removed_packages": removed_packages}

    def consent_options(self, principal: Principal, *, offset: int = 0) -> dict[str, Any]:
        items = self.resources.list_owned(principal, offset=offset)
        for item in items:
            item["actions"] = sorted({"download"} if item["kind"] == "package" else COLLECTION_ACTIONS)
        return {
            "workspace": {"resource_id": workspace_id(principal), "generation": "workspace_v1",
                          "actions": sorted(WORKSPACE_ACTIONS)},
            "resources": items, "offset": offset,
            "next_offset": offset + len(items) if len(items) == 50 else None,
            "policies": self.policies.as_dict(),
            "recipient": "configured_operator_and_chatgpt" if self.configuration.mode == "oauth" else "local_operator",
            "max_upload_bytes": self.configuration.max_upload_bytes,
            "upload_lifetime_seconds": self.uploads.limits.lifetime_seconds,
            "artifact_lifetime_seconds": self.configuration.retention_seconds,
        }

    def prepare_consent(
        self, principal: Principal, *, resource_id: str, generation: str, actions: list[str],
    ) -> Grant:
        self._require_metadata_capacity()
        if resource_id == workspace_id(principal) and generation == "workspace_v1":
            allowed = WORKSPACE_ACTIONS
        else:
            resource = self.resources.resolve(principal, resource_id, generation)
            allowed = frozenset({"download"}) if resource.kind == "package" else COLLECTION_ACTIONS
        if not isinstance(actions, list) or not actions or len(actions) > len(allowed) or not set(actions) <= allowed:
            raise AccessDenied()
        return self.access.create_grant(
            principal, resource_id=resource_id, generation=generation, actions=actions,
            purpose="eligible_preservation", recipient=("operator_and_chatgpt" if self.configuration.mode == "oauth" else "local_operator"),
            expires_at=int(time.time()) + 3600,
        )

    def _require(self, principal: Principal, resource_id: str, generation: str, action: str, **options):
        return self.access.require_access(principal, resource_id=resource_id, generation=generation, action=action, **options)

    def _require_metadata_capacity(self) -> None:
        # An admission threshold bounds continued pilot growth without silently
        # deleting consent evidence. It is not a filesystem allocation quota.
        if self.database.path.stat().st_size >= 64 * 1024**2:
            raise OperationBusy("The metadata admission threshold requires operator review.")

    def _load(self, resource: Resource) -> LoadedCollection:
        if resource.kind != "collection" or manifest_digest(resource.path) != resource.generation:
            raise ArchiveError("The selected generation is unavailable or changed.")
        collection = load_collection(resource.path, limits=ARCHIVE_LIMITS)
        if manifest_digest(resource.path) != resource.generation:
            raise ArchiveError("The selected generation changed during verification.")
        return collection

    def _require_origin(
        self, principal: Principal, resource_id: str, connection: sqlite3.Connection | None = None,
    ) -> None:
        # Derived collections retain their authorization lineage. A package or
        # another generation must not become a route around a revoked ancestor.
        # All grant checks share the caller's transaction at publication time.
        seen: set[str] = set()
        with (nullcontext(connection) if connection is not None else self.database.transaction(immediate=False)) as current:
            while resource_id != workspace_id(principal):
                if resource_id in seen or len(seen) >= 64:
                    raise AccessDenied()
                seen.add(resource_id)
                operation_id = self.resources.origin_operation(resource_id, current)
                if operation_id is None:
                    return
                operation = self.operations.get(principal.principal_id, operation_id, connection=current)
                if operation.state not in {"completed", "partial"} or operation.result is None:
                    raise AccessDenied()
                plan = self.operations.get_plan(principal.principal_id, operation.plan_id, connection=current)
                self._require_current_plan_scope(current, plan)
                resource_id = plan.scope.resource_id

    def list_collections(
        self, principal: Principal, *, after_grant_id: str | None = None, limit: int = 20,
    ) -> dict[str, Any]:
        grants = self.access.list_grants(principal, action="browse", after_grant_id=after_grant_id, limit=limit)
        items = []
        for grant in grants:
            try:
                resource = self.resources.resolve(principal, grant.resource_id, grant.generation)
                self._require_origin(principal, grant.resource_id)
                if resource.kind == "collection":
                    items.append({"collection_id": grant.resource_id, "generation": grant.generation})
            except AccessDenied:
                continue
        return {"items": items, "limit": limit,
                "next_grant_id": grants[-1].grant_id if len(grants) == limit else None,
                "content_inspected": False}

    def query(
        self, principal: Principal, collection_id: str, generation: str, action: str,
        execute: Callable[[LoadedCollection], dict[str, Any]],
    ) -> dict[str, Any]:
        decision = self._require(principal, collection_id, generation, action)
        resource = self.resources.resolve(principal, collection_id, generation)
        self._require_origin(principal, collection_id)
        if not self._io.acquire(blocking=False):
            raise OperationBusy("A content operation is already in progress.")
        try:
            result = execute(self._load(resource))
            self._require(principal, collection_id, generation, action, grant_id=decision.grant_id,
                          expected_grant_version=decision.grant_version,
                          expected_acceptance_id=decision.acceptance_id)
            self._require_origin(principal, collection_id)
            return result
        finally:
            self._io.release()

    def receive_upload(
        self, principal: Principal, source: BinaryIO, *, display_name: str,
        expected_size_bytes: int | None = None,
    ) -> dict[str, Any]:
        decision = self._require(principal, workspace_id(principal), "workspace_v1", "upload")
        next_check = 0.0

        def check() -> None:
            nonlocal next_check
            if time.monotonic() >= next_check:
                self._require(principal, workspace_id(principal), "workspace_v1", "upload",
                              grant_id=decision.grant_id, expected_grant_version=decision.grant_version,
                              expected_acceptance_id=decision.acceptance_id)
                next_check = time.monotonic() + 0.25

        record = self.uploads.receive(principal.principal_id, source, display_name=display_name,
                                      expected_size_bytes=expected_size_bytes, checkpoint=check)
        try:
            self._require(principal, workspace_id(principal), "workspace_v1", "upload",
                          grant_id=decision.grant_id, expected_grant_version=decision.grant_version,
                          expected_acceptance_id=decision.acceptance_id)
        except AccessDenied:
            self.uploads.discard(principal.principal_id, record.upload_id)
            raise
        result = record.as_dict()
        result.pop("owner_id")
        return result

    def prepare(
        self, principal: Principal, *, resource_id: str, generation: str, parameters: OperationParameters,
    ) -> OperationPlan:
        self._require_metadata_capacity()
        action = {ImportParameters: "import", RecoveryParameters: "recover", AssociationParameters: "associate",
                  PackageParameters: "package", UnpackParameters: "unpack"}.get(type(parameters))
        if action is None:
            raise AccessDenied()
        decision = self._require(principal, resource_id, generation, action)
        if isinstance(parameters, (ImportParameters, UnpackParameters)):
            record = self.uploads.resolve(principal.principal_id, parameters.input_handle)
            if record.sha256 != parameters.input_sha256:
                raise AccessDenied()
        if resource_id != workspace_id(principal):
            self.resources.resolve(principal, resource_id, generation)
            self._require_origin(principal, resource_id)
        elif generation != "workspace_v1" or not isinstance(parameters, (ImportParameters, UnpackParameters)):
            raise AccessDenied()
        if isinstance(parameters, ImportParameters):
            if (parameters.previous_generation is None) != (resource_id == workspace_id(principal)):
                raise AccessDenied()
            if parameters.previous_generation is not None and parameters.previous_generation != generation:
                raise AccessDenied()
        scope = AuthorizationScope(resource_id, generation, decision.grant_id, decision.grant_version,
                                   decision.acceptance_id, action)
        return self.operations.prepare(principal.principal_id, parameters, scope=scope,
                                       reservation_bytes=OPERATION_RESERVATION_BYTES, authorize=self._authorize)

    def _authorize(self, connection: sqlite3.Connection, plan: OperationPlan) -> None:
        self._require_plan_scope(connection, plan)
        self._require_origin(self.principal(plan.principal_id), plan.scope.resource_id, connection)

    def _require_plan_scope(self, connection: sqlite3.Connection, plan: OperationPlan) -> None:
        principal = self.principal(plan.principal_id)
        scope = plan.scope
        self._require(principal, scope.resource_id, scope.generation, scope.action,
                      grant_id=scope.grant_id, expected_grant_version=scope.grant_version,
                      expected_acceptance_id=scope.acceptance_id, connection=connection)
        if isinstance(plan.parameters, ImportParameters) and plan.parameters.previous_generation is not None:
            # Intake consent is independently revocable. A fresh deliberate
            # acceptance can authorize the same workspace while the immutable
            # source-generation grant remains fenced by the reviewed plan.
            self._require(principal, workspace_id(principal), "workspace_v1", "import", connection=connection)

    def _require_current_plan_scope(self, connection: sqlite3.Connection, plan: OperationPlan) -> None:
        """Authorize disclosure from a completed operation under current consent.

        Historical plans remain immutable. A human may explicitly renew each
        ancestor's exact resource, generation, and action after an old grant
        expires or is withdrawn. Permission on a child alone cannot renew that
        ancestor. Queued and running operations continue to use the stricter
        reviewed grant/version/receipt fence in _require_plan_scope.
        """
        principal = self.principal(plan.principal_id)
        scope = plan.scope
        self._require(principal, scope.resource_id, scope.generation, scope.action, connection=connection)
        if isinstance(plan.parameters, ImportParameters) and plan.parameters.previous_generation is not None:
            self._require(principal, workspace_id(principal), "workspace_v1", "import", connection=connection)

    def start(self, principal: Principal, plan_id: str, idempotency_key: str) -> dict[str, Any]:
        snapshot = self.operations.start(principal.principal_id, plan_id,
                                         idempotency_key=idempotency_key, authorize=self._authorize, admit=self._admit)
        self.worker.notify()
        return self.status(principal, snapshot.operation_id)

    def _admit(self, connection: sqlite3.Connection, plan: OperationPlan) -> None:
        self._require_metadata_capacity()
        if shutil.disk_usage(self.root).free < OPERATION_RESERVATION_BYTES:
            raise OperationBusy("Insufficient free storage for the operation reservation.")
        # Reserve the entire upload pool independently; admission cannot depend
        # on a stale reading of a concurrently changing second SQLite ledger.
        required = (self.resources.stored_bytes(connection) + self.operations.reserved_bytes(connection)
                    + plan.reservation_bytes + self.uploads.limits.max_total_bytes)
        if required > self.configuration.max_storage_bytes:
            raise OperationBusy("The configured managed-storage budget is exhausted.")

    def status(self, principal: Principal, operation_id: str) -> dict[str, Any]:
        snapshot = self.operations.get(principal.principal_id, operation_id)
        result = snapshot.as_dict()
        try:
            plan = self.operations.get_plan(principal.principal_id, snapshot.plan_id)
            with self.database.transaction(immediate=False) as connection:
                if snapshot.state in {"completed", "partial"}:
                    self._require_current_plan_scope(connection, plan)
                    self._require_origin(principal, plan.scope.resource_id, connection)
                else:
                    self._authorize(connection, plan)
        except AccessDenied:
            result["output_id"], result["result"] = None, None
            result["disclosure"] = "authorization_required"
        return result

    def _collection_result(self, path: Path) -> VerifiedResult:
        collection = load_collection(path, limits=ARCHIVE_LIMITS)
        return VerifiedResult(manifest_digest(path), len(collection.manifest.files),
                              sum(item.size_bytes for item in collection.manifest.files), _coverage(collection))

    def _package_result(self, path: Path) -> VerifiedResult:
        if {item.name for item in path.iterdir()} != {"manifest.json", "package.zip"}:
            raise ArchiveError("The delivery directory has unexpected entries.")
        with open_regular(path / "manifest.json") as source:
            data = source.read(16 * 1024 + 1)
        if len(data) > 16 * 1024:
            raise ArchiveError("The delivery receipt exceeds its byte limit.")
        receipt = json.loads(data)
        if set(receipt) != {"format", "package"} or receipt["format"] != "lpx-keepmorrow.delivery.v1":
            raise ArchiveError("The delivery receipt is unsupported.")
        digest, size = _file_digest(path / "package.zip", 1024**3)
        if digest != receipt["package"]["sha256"] or size != receipt["package"]["size_bytes"]:
            raise ArchiveError("The delivery artifact does not match its receipt.")
        # A ZIP digest alone cannot prove the enclosed collection contract.
        # Re-open and validate the unchanged package before reconciling a crash.
        with tempfile.TemporaryDirectory(prefix="verify-package-", dir=temporary_parent(self.root / "scratch")) as folder:
            verified = unpack_collection(path / "package.zip", Path(folder) / "collection", archive_limits=ARCHIVE_LIMITS)
            gaps = _coverage(load_collection(Path(folder) / "collection", limits=ARCHIVE_LIMITS))
        if verified.manifest_sha256 != receipt["package"]["manifest_sha256"]:
            raise ArchiveError("The enclosed collection differs from its receipt.")
        return VerifiedResult(hashlib.sha256(data).hexdigest(), verified.file_count,
                              size, gaps, artifact_sha256=digest)

    def _inspect_interrupted(self, snapshot: OperationSnapshot) -> VerifiedResult | None:
        destination = self.resources.output_root / snapshot.output_id
        if not os.path.lexists(destination):
            return None
        safe_directory(destination)
        with self.workspaces.workspace(snapshot.operation_id, snapshot.output_id) as scratch:
            with execution_scope(checkpoint=lambda: None, temporary_root=scratch):
                result = self._package_result(destination) if snapshot.kind == "package" else self._collection_result(destination)
        if result.manifest_sha256 != snapshot.manifest_sha256:
            raise ArchiveError("The interrupted output does not match its publication decision.")
        self._register(snapshot, result)
        return result

    def _register(self, snapshot: OperationSnapshot, result: VerifiedResult) -> None:
        self.resources.register_output(
            snapshot.principal_id, output_id=snapshot.output_id, generation=result.manifest_sha256,
            kind="package" if snapshot.kind == "package" else "collection", operation_id=snapshot.operation_id,
            expires_at=(int(snapshot.created_at) + self.configuration.retention_seconds if snapshot.kind == "package" else None),
            stored_bytes=result.total_bytes + (self.resources.output_root / snapshot.output_id / "manifest.json").stat().st_size,
        )

    def _execute(self, attempt: OperationAttempt) -> None:
        while not self._io.acquire(timeout=0.25):
            attempt.checkpoint()
            with self.database.transaction(immediate=False) as connection:
                self._authorize(connection, attempt.plan)
        try:
            with self.workspaces.workspace(attempt.operation_id, attempt.output_id) as scratch:
                with execution_scope(checkpoint=lambda: None, temporary_root=scratch):
                    self._execute_owned(attempt, scratch)
        finally:
            # The workspace marker and temporary bytes remain exclusively owned
            # until cleanup finishes, including after completed status is stored.
            self._io.release()

    def _execute_owned(self, attempt: OperationAttempt, scratch: Path) -> None:
        plan = attempt.plan
        principal = self.principal(plan.principal_id)
        destination = self.resources.output_root / attempt.output_id
        next_check = 0.0

        def check() -> None:
            nonlocal next_check
            if time.monotonic() >= next_check:
                attempt.checkpoint()
                with self.database.transaction(immediate=False) as connection:
                    self._authorize(connection, plan)
                next_check = time.monotonic() + 0.25

        def authorize(stage: Path, target: Path) -> None:
            if target != destination:
                return
            attempt.checkpoint(verifying=True)
            attempt.authorize_publication(self._authorize, manifest_sha256=manifest_digest(stage))

        with self.database.transaction(immediate=False) as connection:
            self._authorize(connection, plan)
        with execution_scope(checkpoint=check, before_publish=authorize, temporary_root=scratch):
            parameters = plan.parameters
            if isinstance(parameters, (ImportParameters, UnpackParameters)):
                with self.uploads.borrow_path(plan.principal_id, parameters.input_handle, checkpoint=check) as input_path:
                    record = self.uploads.resolve(plan.principal_id, parameters.input_handle)
                    if record.sha256 != parameters.input_sha256:
                        raise ArchiveError("The reviewed upload changed identity.")
                    if isinstance(parameters, UnpackParameters):
                        unpack_collection(input_path, destination, archive_limits=ARCHIVE_LIMITS, checkpoint=check)
                    else:
                        previous = None
                        if parameters.previous_generation is not None:
                            source = self.resources.resolve(principal, plan.scope.resource_id, plan.scope.generation)
                            self._load(source)
                            previous = source.path
                        import_exports([input_path], destination, account_namespace=parameters.account_namespace,
                                       previous=previous, limits=ARCHIVE_LIMITS)
            else:
                source = self.resources.resolve(principal, plan.scope.resource_id, plan.scope.generation)
                self._require_origin(principal, source.resource_id)
                self._load(source)
                if isinstance(parameters, RecoveryParameters):
                    recover_selection(source.path, destination, conversation_keys=parameters.conversation_keys,
                                      project_id=parameters.project_id, revision_id=parameters.revision_id,
                                      limits=ARCHIVE_LIMITS)
                elif isinstance(parameters, AssociationParameters):
                    associate_conversation(source.path, destination, **asdict(parameters), limits=ARCHIVE_LIMITS)
                elif isinstance(parameters, PackageParameters):
                    with tempfile.TemporaryDirectory(prefix="delivery-", dir=scratch) as folder:
                        stage = Path(folder)
                        packed = pack_collection(source.path, stage / "package.zip", archive_limits=ARCHIVE_LIMITS,
                                                 checkpoint=check)
                        receipt = {"format": "lpx-keepmorrow.delivery.v1", "package": packed.as_dict()}
                        (stage / "manifest.json").write_bytes(json.dumps(receipt, sort_keys=True).encode("utf-8"))
                        publish_directory(stage, destination)
                else:
                    raise AccessDenied()
        # Publication authorization is the cancellation cutoff. A later
        # revocation may prevent delivery but cannot relabel already
        # published verified bytes as an unstarted or canceled operation.
        result = self._package_result(destination) if plan.kind == "package" else self._collection_result(destination)
        snapshot = self.operations.get(plan.principal_id, attempt.operation_id)
        self._register(snapshot, result)
        attempt.complete(result)

    @contextmanager
    def download(self, principal: Principal, resource_id: str, generation: str) -> Iterator[tuple[BinaryIO, int]]:
        decision = self._require(principal, resource_id, generation, "download")
        resource = self.resources.resolve(principal, resource_id, generation)
        self._require_origin(principal, resource_id)
        if resource.kind != "package" or not self._io.acquire(blocking=False):
            raise OperationBusy("The artifact is unavailable or another content operation is in progress.")
        try:
            operation_id = self.resources.origin_operation(resource_id)
            if operation_id is None:
                raise AccessDenied()
            with self.workspaces.workspace(operation_id, resource_id) as scratch:
                with execution_scope(checkpoint=lambda: None, temporary_root=scratch):
                    result = self._package_result(resource.path)
            if result.manifest_sha256 != resource.generation:
                raise ArchiveError("The delivery generation changed.")
            self._require(principal, resource_id, generation, "download", grant_id=decision.grant_id,
                          expected_grant_version=decision.grant_version,
                          expected_acceptance_id=decision.acceptance_id)
            self._require_origin(principal, resource_id)
            with open_regular(resource.path / "package.zip") as stream:
                yield stream, result.total_bytes
        finally:
            self._io.release()
