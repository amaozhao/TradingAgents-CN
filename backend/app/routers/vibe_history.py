from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.routers.account import get_current_user
from app.services.vibe_agent_bridge import get_vibe_agent_path

router = APIRouter()

_SESSION_ID_RE = re.compile(r"^[A-Za-z0-9_-]{8,80}$")
_RUN_ID_RE = re.compile(r"^[0-9]{8}_[0-9]{6}_[0-9]{2}_[A-Za-z0-9]+$")


def _safe_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []

    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            rows.append(value)
    return rows


def _safe_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def _is_child_path(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
    except ValueError:
        return False
    return True


def _run_dirs_from_session(agent_path: Path, session_id: str) -> list[tuple[str, Path]]:
    session_dir = agent_path / "sessions" / session_id
    runs_root = agent_path / "runs"
    if not session_dir.exists() or not _is_child_path(session_dir, agent_path / "sessions"):
        return []

    found: list[tuple[str, Path]] = []
    seen: set[str] = set()

    def add_run(run_id: str | None, run_dir_value: str | None = None) -> None:
        if not run_id or not _RUN_ID_RE.match(run_id) or run_id in seen:
            return
        run_dir = Path(run_dir_value) if run_dir_value else runs_root / run_id
        if not run_dir.is_absolute():
            run_dir = runs_root / run_dir
        if not _is_child_path(run_dir, runs_root):
            return
        if not (run_dir / "trace.jsonl").exists():
            return
        seen.add(run_id)
        found.append((run_id, run_dir))

    for message in _safe_jsonl(session_dir / "messages.jsonl"):
        metadata = message.get("metadata")
        if isinstance(metadata, dict):
            add_run(str(metadata.get("run_id") or "") or None)

    for attempt_file in sorted((session_dir / "attempts").glob("*/attempt.json")):
        attempt = _safe_json(attempt_file)
        run_id = str(attempt.get("run_id") or "") or None
        run_dir = str(attempt.get("run_dir") or "") or None
        add_run(run_id, run_dir)

    return found


def _map_trace_row(row: dict[str, Any], run_id: str, event_id: int) -> dict[str, Any] | None:
    row_type = row.get("type")
    tool = str(row.get("tool") or row.get("tool_name") or "")
    if row_type == "tool_call" and tool:
        payload: dict[str, Any] = {
            "tool_name": tool,
            "tool": tool,
            "arguments": row.get("args") if isinstance(row.get("args"), dict) else {},
            "run_id": run_id,
        }
        if row.get("call_id"):
            payload["call_id"] = row["call_id"]
        if row.get("iter") is not None:
            payload["iter"] = row["iter"]
        return {"event_id": event_id, "event_type": "tool_started", "payload": payload}

    if row_type == "tool_result" and tool:
        status_value = str(row.get("status") or "ok")
        preview = row.get("preview") or row.get("result") or row.get("error") or ""
        payload = {
            "tool_name": tool,
            "tool": tool,
            "status": status_value,
            "elapsed_ms": row.get("elapsed_ms"),
            "preview": preview,
            "result": preview,
            "content": preview,
            "run_id": run_id,
        }
        if row.get("call_id"):
            payload["call_id"] = row["call_id"]
        if row.get("iter") is not None:
            payload["iter"] = row["iter"]
        event_type = "tool_completed" if status_value == "ok" else "tool_failed"
        return {"event_id": event_id, "event_type": event_type, "payload": payload}

    if row_type == "answer_truncated":
        content = row.get("content") or row.get("text") or ""
        payload = {
            "content": str(content),
            "run_id": run_id,
            "truncated": True,
        }
        if row.get("iter") is not None:
            payload["iter"] = row["iter"]
        return {"event_id": event_id, "event_type": "assistant_delta", "payload": payload}

    return None


def load_session_trace_events(agent_path: Path, session_id: str) -> list[dict[str, Any]]:
    if not _SESSION_ID_RE.match(session_id):
        return []

    events: list[dict[str, Any]] = []
    next_event_id = 1
    for run_id, run_dir in _run_dirs_from_session(agent_path, session_id):
        for row in _safe_jsonl(run_dir / "trace.jsonl"):
            event = _map_trace_row(row, run_id, next_event_id)
            if event is None:
                continue
            events.append(event)
            next_event_id += 1
    return events


@router.get("/sessions/{session_id}/events")
async def list_vibe_history_events(
    session_id: str,
    after_event_id: int = Query(0, ge=0),
    current_user: dict = Depends(get_current_user),
):
    if not current_user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    agent_path = get_vibe_agent_path()
    if agent_path is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vibe agent not found")

    events = load_session_trace_events(agent_path, session_id)
    if after_event_id:
        events = [event for event in events if int(event.get("event_id") or 0) > after_event_id]
    return events
