"""Bound JSON decoding work before constructing Python object graphs.

Copyright 2026 Lopix Neural Inc. All rights reserved.
"""

from __future__ import annotations

from ..archive.model import ArchiveError
from ..control import checkpoint


def check_json_budget(data: bytes, *, max_bytes: int, max_depth: int, max_tokens: int) -> None:
    """Check byte, lexical-token, and container-depth ceilings in O(B) time.

    This constant-space pass bounds allocation-driving syntax before a JSON
    decoder materializes containers and values. Quoted braces, escaped quotes,
    and whitespace do not inflate structural depth or token counts. Tokens
    conservatively include separators and closing delimiters; a configured
    token budget is not a promise about peak process memory.

    This is a resource boundary, not a JSON grammar or Unicode validator. The
    caller must subsequently decode with its own duplicate-key, finite-number,
    Unicode, and schema policy. Malformed syntax can pass this check and must
    still fail decoding. Raise ArchiveError for invalid budgets or excess work.
    """
    if not isinstance(data, bytes):
        raise ArchiveError("JSON budget checks require immutable input bytes.")
    for name, value in (("max_bytes", max_bytes), ("max_depth", max_depth), ("max_tokens", max_tokens)):
        if type(value) is not int or value <= 0:
            raise ArchiveError(f"{name} must be a positive integer.")
    if len(data) > max_bytes:
        raise ArchiveError("The JSON document exceeds the configured byte limit.")

    depth = tokens = 0
    in_string = escaped = in_atom = False
    for offset, byte in enumerate(data):
        if offset & 65535 == 0:
            checkpoint()
        if in_string:
            if escaped:
                escaped = False
            elif byte == 92:
                escaped = True
            elif byte == 34:
                in_string = False
            continue
        if byte == 34:
            in_string, in_atom = True, False
            tokens += 1
        elif byte in (123, 91):
            depth += 1
            tokens += 1
            in_atom = False
            if depth > max_depth:
                raise ArchiveError("The JSON document exceeds the configured nesting limit.")
        elif byte in (125, 93):
            depth -= 1
            tokens += 1
            in_atom = False
        elif byte in (44, 58):
            tokens += 1
            in_atom = False
        elif byte in (9, 10, 13, 32):
            in_atom = False
        elif not in_atom:
            tokens += 1
            in_atom = True
        if tokens > max_tokens:
            raise ArchiveError("The JSON document exceeds the configured token limit.")
