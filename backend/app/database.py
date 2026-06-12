"""Compatibility wrapper for database helpers.

The app database layer was moved under ``app.core.database``. Some existing
tests and scripts still import ``app.database``.
"""

from app.core import database as _database

__all__ = [name for name in dir(_database) if not name.startswith("_")]
globals().update({name: getattr(_database, name) for name in __all__})
