"""Optional, read-only local MCP adapter for future ChatGPT integration."""

from .registry import RegistryError, load_registry
from .server import create_server

__all__ = ["RegistryError", "create_server", "load_registry"]
