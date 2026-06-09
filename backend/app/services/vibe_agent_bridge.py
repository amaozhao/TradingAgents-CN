from __future__ import annotations

import importlib
import sys
from pathlib import Path

from fastapi import FastAPI


def _default_vibe_agent_path() -> Path:
    return Path(__file__).resolve().parents[4] / "Vibe-Trading" / "agent"


def load_vibe_app() -> FastAPI | None:
    """Load the local Vibe-Trading FastAPI app when the source tree is present."""
    agent_path = _default_vibe_agent_path()
    if not agent_path.exists():
        return None

    path_text = str(agent_path)
    if path_text not in sys.path:
        sys.path.insert(0, path_text)

    module = importlib.import_module("api_server")
    app = getattr(module, "app", None)
    if isinstance(app, FastAPI):
        return app
    return None
