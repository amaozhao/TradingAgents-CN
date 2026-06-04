"""
Sync router for stock basics synchronization
- POST /api/sync/stock_basics/run -> trigger full sync
- GET  /api/sync/stock_basics/status -> get last status
Requires PostgreSQL initialized by app lifespan.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.sync.basic import get_basics_sync_service

router = APIRouter(prefix="/api/sync", tags=["sync"])


class SyncApiResponse(BaseModel):
    success: bool
    data: Any


@router.post("/stock_basics/run", response_model=SyncApiResponse)
async def run_stock_basics_sync(force: bool = False):
    try:
        service = get_basics_sync_service()
        result = await service.run_full_sync(force=force)
        return {"success": True, "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stock_basics/status", response_model=SyncApiResponse)
async def get_stock_basics_status():
    service = get_basics_sync_service()
    status = await service.get_status()
    return {"success": True, "data": status}
