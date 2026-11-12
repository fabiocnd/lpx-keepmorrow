"""Optional ChatGPT adapters with separate development and authenticated modes.

The package exports the legacy read-only loopback factory for compatibility.
The authenticated service and trusted portal are composed by ``application``;
importing this package does not deploy either integration.
"""

from .registry import RegistryError, load_registry
from .server import create_server

__all__ = ["RegistryError", "create_server", "load_registry"]
