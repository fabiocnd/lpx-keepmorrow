"""Explicit local operations with acceptance before selected-content inspection.

Status commands omit conversation bodies. Browse, search, and read return only
the content deliberately requested by that operation; they are not telemetry.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

from .archive import ArchiveError, create_archive, restore_archive, verify_archive
from .catalog.query import browse_catalog, read_revision, search_catalog
from .catalog.service import (
    associate_conversation, import_exports, load_collection, recover_selection,
)
from .consent import (
    CURRENT_PRIVACY_VERSION, CURRENT_TERMS_VERSION, ConsentError, require_acceptance,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="keepmorrow", description="Preserve and inspect explicitly supplied AI work.")
    operations = parser.add_subparsers(dest="operation", required=True)
    create = operations.add_parser("create", help="Create a new portable directory archive.")
    create.add_argument("source", type=Path)
    create.add_argument("destination", type=Path)
    verify = operations.add_parser("verify", help="Verify local archive bytes and inventory.")
    verify.add_argument("archive", type=Path)
    verify.add_argument("--collection", action="store_true", help="Also validate the semantic collection contract.")
    restore = operations.add_parser("restore", help="Recover the complete payload into a new directory.")
    restore.add_argument("archive", type=Path)
    restore.add_argument("destination", type=Path)

    intake = operations.add_parser("import", help="Preserve selected export folders or ZIPs and build a catalog.")
    intake.add_argument("sources", nargs="+", type=Path)
    intake.add_argument("--destination", type=Path, required=True)
    intake.add_argument("--account-namespace", required=True, help="Stable local label for this source account.")
    intake.add_argument("--previous", type=Path, help="Extend a verified collection into a separate new generation.")
    catalog = operations.add_parser("catalog", help="Browse bounded conversation metadata.")
    catalog.add_argument("archive", type=Path)
    catalog.add_argument("--offset", type=int, default=0)
    catalog.add_argument("--limit", type=int, default=50)
    catalog.add_argument("--project-id")
    catalog.add_argument("--association-state", choices=("project_confirmed", "standalone_confirmed", "association_unknown"))
    search = operations.add_parser("search", help="Search retained titles and message text literally.")
    search.add_argument("archive", type=Path)
    search.add_argument("query")
    search.add_argument("--limit", type=int, default=20)
    search.add_argument("--conversation-key")
    read = operations.add_parser("read", help="Read a bounded page of one conversation revision.")
    read.add_argument("archive", type=Path)
    read.add_argument("conversation_key")
    read.add_argument("--revision-id")
    read.add_argument("--offset", type=int, default=0)
    read.add_argument("--limit", type=int, default=50)
    associate = operations.add_parser("associate", help="Record a classification in a separate new generation.")
    associate.add_argument("archive", type=Path)
    associate.add_argument("destination", type=Path)
    associate.add_argument("--conversation-key", required=True)
    associate.add_argument("--state", choices=("project_confirmed", "standalone_confirmed", "association_unknown"), required=True)
    associate.add_argument("--project-id")
    associate.add_argument("--reason", required=True)
    recover = operations.add_parser("recover", help="Package selected conversations and available bound artifacts.")
    recover.add_argument("archive", type=Path)
    recover.add_argument("destination", type=Path)
    selection = recover.add_mutually_exclusive_group(required=True)
    selection.add_argument("--conversation-key", action="append", default=[])
    selection.add_argument("--project-id")
    recover.add_argument("--revision-id")

    for operation in (create, verify, restore, intake, catalog, search, read, associate, recover):
        operation.add_argument("--accept-terms", metavar="VERSION",
                               help=f"Accept legal/terms-of-use.md, version {CURRENT_TERMS_VERSION}.")
        operation.add_argument("--accept-privacy", metavar="VERSION",
                               help=f"Accept legal/privacy-notice.md, version {CURRENT_PRIVACY_VERSION}.")
    return parser


def _execute(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    if args.operation == "verify":
        if args.collection:
            collection = load_collection(args.archive)
            return {"stage": "collection_validation", "verified": True,
                    "summary": collection.document["summary"], "account_completeness": "not_asserted"}, 0
        report = verify_archive(args.archive)
        return report.as_dict(), 0 if report.verified else 1
    if args.operation in {"create", "restore"}:
        if args.operation == "create":
            manifest = create_archive(args.source, args.destination)
            stage = "local_archive_validation"
        else:
            manifest = restore_archive(args.archive, args.destination)
            stage = "recovery_validation"
        return {"stage": stage, "verified": True, "file_count": len(manifest.files),
                "total_bytes": sum(item.size_bytes for item in manifest.files)}, 0
    if args.operation in {"catalog", "search", "read"}:
        document = load_collection(args.archive).document
        if args.operation == "catalog":
            result = browse_catalog(document, offset=args.offset, limit=args.limit,
                                    project_id=args.project_id, association_state=args.association_state)
        elif args.operation == "search":
            result = search_catalog(document, args.query, limit=args.limit, conversation_key=args.conversation_key)
        else:
            result = read_revision(document, args.conversation_key, revision_id=args.revision_id,
                                   offset=args.offset, limit=args.limit)
        return {"stage": "verified_collection_query", "result": result}, 0
    if args.operation == "import":
        outcome = import_exports(args.sources, args.destination, account_namespace=args.account_namespace,
                                 previous=args.previous)
    elif args.operation == "associate":
        outcome = associate_conversation(args.archive, args.destination, conversation_key=args.conversation_key,
                                         state=args.state, project_id=args.project_id, reason=args.reason)
    else:
        outcome = recover_selection(args.archive, args.destination, conversation_keys=args.conversation_key,
                                    project_id=args.project_id, revision_id=args.revision_id)
    return outcome.as_dict(), 0 if outcome.semantic_status == "complete" else 3


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    # Parsing paths does not inspect them. Exact policy versions are checked
    # before resolving a source, loading a catalog, or creating a staging tree.
    try:
        receipt = require_acceptance(args.accept_terms, args.accept_privacy, args.operation)
    except ConsentError as error:
        print(json.dumps({"operation": args.operation, "error_code": "acceptance_required", "error": str(error)},
                         sort_keys=True), file=sys.stderr)
        return 2
    try:
        result, status = _execute(args)
        print(json.dumps({**result, "operation": args.operation, "acceptance": receipt.as_dict()},
                         sort_keys=True, ensure_ascii=True, allow_nan=False))
        return status
    except (ArchiveError, OSError) as error:
        print(json.dumps({"operation": args.operation, "error": str(error), "acceptance": receipt.as_dict()},
                         sort_keys=True), file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print(json.dumps({"operation": args.operation, "error_code": "cancelled",
                          "error": "The operation was cancelled; no completed result is asserted.",
                          "acceptance": receipt.as_dict()}, sort_keys=True), file=sys.stderr)
        return 130

