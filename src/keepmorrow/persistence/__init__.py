"""Shared transactional metadata storage for the private service.

Copyright 2026 Lopix Neural Inc. All rights reserved.
"""

from .sqlite import PersistenceError, SQLiteDatabase

__all__ = ["PersistenceError", "SQLiteDatabase"]
