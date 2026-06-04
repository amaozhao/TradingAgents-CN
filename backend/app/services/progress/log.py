"""
Thin re-export: ProgressLogHandler moved to app.services.progress.handler
This module keeps exports for backward compatibility. Prefer importing from the new path.
"""

from app.services.progress.handler import (
    ProgressLogHandler,
    get_logs,
    register_analysis_tracker,
    unregister_analysis_tracker,
)

__all__ = [
    "ProgressLogHandler",
    "get_logs",
    "register_analysis_tracker",
    "unregister_analysis_tracker",
]
