from __future__ import annotations

import re
import uuid
from typing import Any

_DOCUMENT_ID_PATTERN = re.compile(r"^[0-9a-fA-F]{24}$")


class DocumentId(str):
    """String-backed 24-hex identifier used by PostgreSQL document storage."""

    def __new__(cls, value: Any | None = None):
        text = uuid.uuid4().hex[:24] if value is None else str(value)
        if not cls.is_valid(text):
            raise ValueError("Invalid DocumentId")
        return str.__new__(cls, text.lower())

    @classmethod
    def is_valid(cls, value: Any) -> bool:
        return bool(_DOCUMENT_ID_PATTERN.fullmatch(str(value)))
