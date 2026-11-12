"""Explicit local archive operations; output contains status, never file content."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from .archive import ArchiveError, create_archive, restore_archive, verify_archive
from .consent import (
    CURRENT_PRIVACY_VERSION,
    CURRENT_TERMS_VERSION,
    ConsentError,
    require_acceptance,
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="keepmorrow", description="Preserve explicitly supplied local files.")
    operations = parser.add_subparsers(dest="operation", required=True)
    create = operations.add_parser("create", help="Create a new portable directory archive.")
    create.add_argument("source", type=Path)
    create.add_argument("destination", type=Path)
    verify = operations.add_parser("verify", help="Verify local archive bytes and inventory.")
    verify.add_argument("archive", type=Path)
    restore = operations.add_parser("restore", help="Recover into a new, separate directory.")
    restore.add_argument("archive", type=Path)
    restore.add_argument("destination", type=Path)
    for operation_parser in (create, verify, restore):
        operation_parser.add_argument(
            "--accept-terms", metavar="VERSION",
            help=f"Accept legal/terms-of-use.md, version {CURRENT_TERMS_VERSION}.",
        )
        operation_parser.add_argument(
            "--accept-privacy", metavar="VERSION",
            help=f"Accept legal/privacy-notice.md, version {CURRENT_PRIVACY_VERSION}.",
        )
    args = parser.parse_args(argv)

    # Path arguments are still inert values here. Refuse before even checking
    # whether a selected source or archive exists, so refusal reveals no state.
    try:
        receipt = require_acceptance(args.accept_terms, args.accept_privacy, args.operation)
    except ConsentError as error:
        print(json.dumps({"operation": args.operation, "error_code": "acceptance_required",
                          "error": str(error)}, sort_keys=True), file=sys.stderr)
        return 2

    try:
        if args.operation == "verify":
            report = verify_archive(args.archive)
            print(json.dumps({**report.as_dict(), "operation": args.operation,
                              "acceptance": receipt.as_dict()}, sort_keys=True))
            return 0 if report.verified else 1
        if args.operation == "create":
            manifest = create_archive(args.source, args.destination)
            stage = "local_archive_validation"
        else:
            manifest = restore_archive(args.archive, args.destination)
            stage = "recovery_validation"
        print(json.dumps({"operation": args.operation, "stage": stage, "verified": True,
                          "file_count": len(manifest.files),
                          "total_bytes": sum(item.size_bytes for item in manifest.files),
                          "acceptance": receipt.as_dict()}, sort_keys=True))
        return 0
    except (ArchiveError, OSError) as error:
        print(json.dumps({"operation": args.operation, "error": str(error),
                          "acceptance": receipt.as_dict()}, sort_keys=True), file=sys.stderr)
        return 2

