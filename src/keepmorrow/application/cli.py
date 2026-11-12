"""Explicit local setup and service lifecycle commands for the private pilot.

Copyright 2026 Lopix Neural Inc. All rights reserved.
"""

from __future__ import annotations

import argparse
from importlib.resources import files
import json
import os
from pathlib import Path
import secrets
import sys
from typing import Sequence

from ..access import Principal
from ..archive.filesystem import safe_directory
from ..archive.model import ArchiveError
from ..catalog.service import load_collection
from ..consent import ConsentError, require_acceptance
from .configuration import ConfigurationError, Resource, load_configuration
from .service import manifest_digest


def _write_new(path: Path, data: bytes) -> None:
    descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_BINARY", 0), 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(data)


def _initialize(args) -> dict[str, object]:
    root = args.directory.absolute()
    safe_directory(root.parent)
    root.mkdir(mode=0o700)
    policy_root = root / "policies"
    policy_root.mkdir(mode=0o700)
    for name in ("terms-of-use.md", "privacy-notice.md"):
        _write_new(policy_root / name, files("keepmorrow").joinpath("policies", name).read_bytes())
    identity = Principal("urn:lpx-keepmorrow:local-operator", args.operator)
    _write_new(root / "operator.key", (secrets.token_hex(32) + "\n").encode("ascii"))
    configuration = {
        "state_directory": str(root), "policy_directory": str(policy_root), "mode": "operator", "port": args.port,
        "public_origin": f"http://127.0.0.1:{args.port}", "principals": [{"issuer": identity.issuer, "subject": identity.subject}],
        "resources": [],
    }
    _write_new(root / "service.json", (json.dumps(configuration, indent=2) + "\n").encode("utf-8"))
    load_configuration(root / "service.json")
    return {"status": "initialized", "mode": "operator", "configuration": str(root / "service.json"),
            "operator_key_file": str(root / "operator.key"), "content_processed": False,
            "mcp_enabled": False, "message": "Protect the operator key. Enter it only in your local portal."}


def _registration(args) -> dict[str, object]:
    require_acceptance(args.accept_terms, args.accept_privacy, "verify")
    configuration = load_configuration(args.configuration)
    principal = next((item for item in configuration.principals if item.subject == args.subject), None)
    if principal is None:
        raise ConfigurationError("The selected identity is not allowlisted.")
    selected = args.collection.absolute()
    # Registration is itself a deliberate local verification action. The
    # connected service still requires a separate human scope acceptance.
    load_collection(selected)
    resource = Resource(args.identifier, manifest_digest(selected), principal.principal_id, selected)
    if any(item.resource_id == resource.resource_id for item in configuration.resources):
        raise ConfigurationError("The resource identifier is already registered.")
    document = json.loads(args.configuration.read_text(encoding="utf-8"))
    document.setdefault("resources", []).append({"resource_id": resource.resource_id, "generation": resource.generation,
                                                 "principal_id": resource.principal_id, "path": str(resource.path)})
    # A new configuration file is reviewable and cannot replace a concurrently
    # edited operator configuration. Restart explicitly with the selected file.
    _write_new(args.output.absolute(), (json.dumps(document, indent=2) + "\n").encode("utf-8"))
    load_configuration(args.output)
    return {"status": "registered_in_new_configuration", "configuration": str(args.output.absolute()),
            "resource_id": resource.resource_id, "generation": resource.generation, "access_granted": False}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="keepmorrow-service", description="Initialize or run the private preservation pilot.")
    commands = parser.add_subparsers(dest="command", required=True)
    initialize = commands.add_parser("init", help="Create a new local service directory without reading source content.")
    initialize.add_argument("directory", type=Path)
    initialize.add_argument("--operator", default="local-owner", help="Local identity label; not a source-account claim.")
    initialize.add_argument("--port", type=int, default=8765)
    serve = commands.add_parser("serve", help="Run the configured portal and, in OAuth mode, authenticated MCP.")
    serve.add_argument("--configuration", type=Path, required=True)
    check = commands.add_parser("check", help="Validate configuration and policy bytes without opening collections.")
    check.add_argument("--configuration", type=Path, required=True)
    register = commands.add_parser("register", help="Verify one selected collection and write a new configuration.")
    register.add_argument("--configuration", type=Path, required=True)
    register.add_argument("--collection", type=Path, required=True)
    register.add_argument("--identifier", required=True)
    register.add_argument("--subject", required=True)
    register.add_argument("--output", type=Path, required=True)
    register.add_argument("--accept-terms", required=True)
    register.add_argument("--accept-privacy", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "init":
            if not 1 <= args.port <= 65535:
                raise ConfigurationError("The local port is outside its supported range.")
            result = _initialize(args)
        elif args.command == "register":
            result = _registration(args)
        else:
            configuration = load_configuration(args.configuration)
            policies, _ = configuration.policies()
            if args.command == "check":
                result = {"status": "configuration_valid", "mode": configuration.mode,
                          "mcp_enabled": configuration.mode == "oauth", "policies": policies.as_dict(),
                          "collection_content_inspected": False, "live_identity_provider_verified": False,
                          "chatgpt_connection_verified": False}
            else:
                import uvicorn
                from ..integrations.chatgpt.application import create_application
                app = create_application(configuration)
                uvicorn.run(app, host="127.0.0.1", port=configuration.port, access_log=False,
                            log_level="warning", proxy_headers=False, server_header=False,
                            limit_concurrency=32, timeout_keep_alive=5)
                return 0
        print(json.dumps(result, sort_keys=True))
        return 0
    except KeyboardInterrupt:
        return 130
    except (ConfigurationError, ConsentError, ArchiveError, OSError, ValueError, ImportError, RuntimeError):
        print(json.dumps({"error_code": "service_setup_unavailable",
                          "message": "Check explicit configuration, policy versions, private storage, and the installed ChatGPT extra."}),
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
