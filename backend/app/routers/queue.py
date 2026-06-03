from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.routers.account import get_current_user
from app.services.queue.service import get_queue_service, QueueService

router = APIRouter()


class QueueStatsResponse(BaseModel):
    user: str
    queued: int
    processing: int
    completed: int
    failed: int


@router.get("/stats", response_model=QueueStatsResponse)
async def queue_stats(user: dict = Depends(get_current_user), svc: QueueService = Depends(get_queue_service)):
    stats = await svc.stats()
    return {"user": user["id"], **stats}
