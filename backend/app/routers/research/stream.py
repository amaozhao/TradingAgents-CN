from __future__ import annotations

import asyncio
import json
from typing import Any

from app.services.research.agent.events import ResearchEventService


def format_events(events: list[dict[str, Any]]):
    for event in events:
        yield (
            f"id: {event['event_id']}\n"
            f"event: {event['event_type']}\n"
            f"data: {json.dumps(event['payload'], ensure_ascii=False)}\n\n"
        )


async def stream_events(
    *,
    event_service: ResearchEventService,
    session_id: str,
    user_id: str,
    after_event_id: int = 0,
    idle_timeout_seconds: float = 120.0,
):
    last_event_id = int(after_event_id or 0)
    idle_elapsed = 0.0
    poll_interval = 0.5
    terminal_events = {
        "task_completed",
        "task_failed",
        "job_completed",
        "job_failed",
        "attempt.completed",
        "attempt.failed",
        "attempt.cancelled",
    }

    while idle_elapsed < idle_timeout_seconds:
        events = await event_service.list_after(
            session_id=session_id,
            user_id=user_id,
            after_event_id=last_event_id,
        )
        if events:
            idle_elapsed = 0.0
            for chunk in format_events(events):
                yield chunk
            last_event_id = int(events[-1]["event_id"])
            if any(event["event_type"] in terminal_events for event in events):
                return
            continue

        yield "event: heartbeat\ndata: {}\n\n"
        await asyncio.sleep(poll_interval)
        idle_elapsed += poll_interval
