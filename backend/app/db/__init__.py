"""Database access layer.

This package owns repository-style data access and PostgreSQL document-store
compatibility. Runtime session lifecycle and data backfill entry points live in
app.core; Alembic owns schema migrations. SQLAlchemy table models live in
app.models; Pydantic API DTOs live in app.schemas.
"""

from app.models.base import Base

__all__ = ["Base"]
