"""Explicit developer grants for the local ChatGPT development adapter.

Copyright 2026 Lopix Neural Inc. All rights reserved.
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from ...archive.filesystem import open_regular, safe_directory
from ...archive.model import ArchiveError

REGISTRY_FORMAT = "lpx-keepmorrow.chatgpt-registry"
REGISTRY_VERSION = 1
MAX_REGISTRY_BYTES = 1024**2
MAX_COLLECTIONS = 128
_COLLECTION_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}\Z")


class RegistryError(ValueError):
    """The developer's registry does not establish supported explicit grants."""


def valid_collection_id(value: object) -> bool:
    """Accept the opaque registry-token grammar without resolving any path."""
    return isinstance(value, str) and _COLLECTION_ID.fullmatch(value) is not None


def validate_registry(registry: Mapping[str, Path]) -> dict[str, Path]:
    """Copy bounded configuration grants without inspecting collection content.

    Absolute paths are configuration references, not proof of existing or valid
    collections. File opening and integrity checks belong to accepted requests.
    """
    if not isinstance(registry, Mapping) or len(registry) > MAX_COLLECTIONS:
        raise RegistryError("The registry must contain at most 128 collection grants.")
    result: dict[str, Path] = {}
    for identifier, path in registry.items():
        if not valid_collection_id(identifier):
            raise RegistryError("Collection IDs must be opaque alphanumeric, hyphen, or underscore tokens.")
        if not isinstance(path, Path) or not path.is_absolute():
            raise RegistryError("Collection grants require explicit absolute filesystem paths.")
        if len(str(path)) > 4096 or "\x00" in str(path):
            raise RegistryError("A registered path exceeds the supported path contract.")
        result[identifier] = path
    return result


def load_registry(path: Path) -> dict[str, Path]:
    """Read only the explicitly configured registry, never its collection paths.

    The registry is developer configuration, separate from user-content access.
    Tool invocation still requires operation-scoped policy acceptance before a
    configured collection may be resolved, inspected, or read.
    """
    def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise RegistryError("The registry contains duplicate JSON keys.")
            result[key] = value
        return result

    def reject_constant(value: str) -> None:
        raise RegistryError("The registry contains an unsupported JSON number.")

    try:
        parent = safe_directory(path.parent)
        with open_regular(parent / path.name) as source:
            before = os.fstat(source.fileno())
            if before.st_size > MAX_REGISTRY_BYTES:
                raise RegistryError("The registry exceeds the configured byte limit.")
            data = source.read(before.st_size + 1)
            after = os.fstat(source.fileno())
            if (len(data) != before.st_size or before.st_size != after.st_size
                    or before.st_mtime_ns != after.st_mtime_ns or before.st_ctime_ns != after.st_ctime_ns):
                raise RegistryError("The registry changed while it was being read.")
        document = json.loads(data.decode("utf-8"), object_pairs_hook=unique_object,
                              parse_constant=reject_constant)
    except RegistryError:
        raise
    except (ArchiveError, OSError, UnicodeError, ValueError, RecursionError) as error:
        raise RegistryError("The registry could not be read as supported UTF-8 JSON.") from error
    if (not isinstance(document, dict) or set(document) != {"format", "version", "collections"}
            or document["format"] != REGISTRY_FORMAT or type(document["version"]) is not int
            or document["version"] != REGISTRY_VERSION or not isinstance(document["collections"], dict)):
        raise RegistryError("The registry does not match its supported versioned schema.")
    if any(not isinstance(value, str) for value in document["collections"].values()):
        raise RegistryError("Collection grants require explicit absolute filesystem paths.")
    return validate_registry({key: Path(value) for key, value in document["collections"].items()})
