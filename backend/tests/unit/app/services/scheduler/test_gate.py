from __future__ import annotations

import asyncio

import pytest


@pytest.mark.asyncio
async def test_scheduler_gate_serializes_heavy_data_sync_jobs():
    from app.services.scheduler.gate import SchedulerGate

    gate = SchedulerGate(heavy_data_sync_limit=1)
    running = 0
    max_running = 0

    async def run_job():
        nonlocal running, max_running
        async with gate.heavy_data_sync():
            running += 1
            max_running = max(max_running, running)
            await asyncio.sleep(0)
            running -= 1

    await asyncio.gather(run_job(), run_job())

    assert max_running == 1


@pytest.mark.asyncio
async def test_scheduler_gate_allows_light_status_jobs_without_heavy_gate():
    from app.services.scheduler.gate import SchedulerGate

    gate = SchedulerGate(heavy_data_sync_limit=1)

    async with gate.light_status():
        async with gate.light_status():
            assert True
