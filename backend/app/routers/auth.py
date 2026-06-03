"""Compatibility wrapper for the database-backed auth router.

Older tests and integrations import ``app.routers.auth``. The implementation
now lives in ``auth_db``; keep this module as the stable import surface.
"""

from app.routers.account import *  # noqa: F401,F403
