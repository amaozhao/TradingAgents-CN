import json

from app.routers.vibe_history import load_session_trace_events


def test_load_session_trace_events_restores_tool_steps(tmp_path):
    agent_path = tmp_path / "agent"
    session_id = "session123"
    run_id = "20260609_154038_27_e64e7c"
    session_dir = agent_path / "sessions" / session_id
    run_dir = agent_path / "runs" / run_id
    session_dir.mkdir(parents=True)
    run_dir.mkdir(parents=True)

    (session_dir / "messages.jsonl").write_text(
        json.dumps(
            {
                "role": "assistant",
                "content": "done",
                "metadata": {"run_id": run_id, "status": "completed"},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (run_dir / "trace.jsonl").write_text(
        "\n".join(
            [
                json.dumps({"type": "thinking", "content": "plan"}),
                json.dumps(
                    {
                        "type": "tool_call",
                        "tool": "web_read",
                        "call_id": "call-1",
                        "args": {"url": "https://example.com"},
                    }
                ),
                json.dumps(
                    {
                        "type": "tool_result",
                        "tool": "web_read",
                        "call_id": "call-1",
                        "status": "ok",
                        "elapsed_ms": 42,
                        "preview": "No market content.",
                    }
                ),
                json.dumps(
                    {
                        "type": "answer_truncated",
                        "iter": 2,
                        "content": "partial answer before continuation",
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    events = load_session_trace_events(agent_path, session_id)

    assert events == [
        {
            "event_id": 1,
            "event_type": "tool_started",
            "payload": {
                "tool_name": "web_read",
                "tool": "web_read",
                "arguments": {"url": "https://example.com"},
                "call_id": "call-1",
                "run_id": run_id,
            },
        },
        {
            "event_id": 2,
            "event_type": "tool_completed",
            "payload": {
                "tool_name": "web_read",
                "tool": "web_read",
                "status": "ok",
                "elapsed_ms": 42,
                "preview": "No market content.",
                "result": "No market content.",
                "content": "No market content.",
                "call_id": "call-1",
                "run_id": run_id,
            },
        },
        {
            "event_id": 3,
            "event_type": "assistant_delta",
            "payload": {
                "content": "partial answer before continuation",
                "run_id": run_id,
                "truncated": True,
                "iter": 2,
            },
        },
    ]
