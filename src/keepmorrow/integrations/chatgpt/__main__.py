"""Run the development MCP endpoint on loopback with explicit path grants."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from .registry import RegistryError, load_registry
from .server import create_server


def main(argv: Sequence[str] | None = None) -> int:
    """Run the legacy loopback adapter with an operator-supplied registry.

    Registry loading reads configuration only. Collection access remains gated
    by each development tool invocation; this entry point establishes no remote
    identity or authenticated service session.
    """
    parser = argparse.ArgumentParser(
        prog="python -m keepmorrow.integrations.chatgpt",
        description="Run read-only development MCP tools on 127.0.0.1; authenticated deployment is separate.",
    )
    parser.add_argument("--registry", type=Path, required=True,
                        help="Explicit versioned developer registry; never supplied by an MCP tool caller.")
    parser.add_argument("--port", type=int, default=8765, help="Loopback TCP port (default: 8765).")
    args = parser.parse_args(argv)
    try:
        server = create_server(load_registry(args.registry), port=args.port)
        server.run(transport="streamable-http")
    except KeyboardInterrupt:
        return 130
    except (RegistryError, ValueError, RuntimeError, OSError):
        print(json.dumps({"error_code": "development_server_unavailable",
                          "message": "Check the explicit registry, local port, and installed ChatGPT development extra."}),
              file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
