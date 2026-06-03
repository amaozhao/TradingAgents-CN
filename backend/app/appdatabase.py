"""Compatibility wrapper for database helpers.

The app database layer was moved under ``app.core.coredatabase``. Some existing
tests and scripts still import ``app.appdatabase``.
"""

from app.core.coredatabase import *  # noqa: F401,F403
