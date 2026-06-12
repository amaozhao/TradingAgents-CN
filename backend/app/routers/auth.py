"""Compatibility wrapper for the database-backed auth router.

Older tests and integrations import ``app.routers.auth``. The implementation
now lives in ``auth_db``; keep this module as the stable import surface.
"""

from app.routers import account as _account

__all__ = [name for name in dir(_account) if not name.startswith("_")]
globals().update({name: getattr(_account, name) for name in __all__})
