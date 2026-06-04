"""PostgreSQL database infrastructure."""

from importlib import import_module as _import_module

from app.db.base import Base
from support.loader import alias as _alias

_store = _import_module("app.db.store")
documentstore = _alias("app.db.documentstore", _store)

__all__ = ["Base", "documentstore"]

del _alias, _import_module, _store
