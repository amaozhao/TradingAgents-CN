"""Compatibility wrapper for database helpers.

The app database layer was moved under ``app.core.database``. Some existing
tests and scripts still import ``app.database``.
"""

from app.core.database import *  # noqa: F401,F403
