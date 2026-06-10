from __future__ import annotations

from pydantic import BaseModel, Field


class AlphaBenchRequest(BaseModel):
    alpha_id: str = Field(..., min_length=1)
    symbols: list[str] = Field(default_factory=list)
    start_date: str | None = None
    end_date: str | None = None


class AlphaCompareRequest(BaseModel):
    alpha_ids: list[str] = Field(..., min_length=1)
    symbols: list[str] = Field(default_factory=list)
    start_date: str | None = None
    end_date: str | None = None
