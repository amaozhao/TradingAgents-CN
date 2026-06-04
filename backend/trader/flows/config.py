import os
from copy import deepcopy
from pathlib import Path
from typing import Dict, Optional

import trader.default as default_config

# Use default config but allow it to be overridden
_config: Optional[Dict] = None


def initialize_config(force: bool = True):
    """Initialize the configuration with default values."""
    global _config
    if _config is not None and not force:
        return
    _config = deepcopy(default_config.DEFAULT_CONFIG)
    env_data_dir = os.getenv("TRADING_AGENTS_DATA_DIR")
    if env_data_dir:
        _config["data_dir"] = env_data_dir
    _ensure_data_dir_structure(_config.get("data_dir"))


def set_config(config: Dict):
    """Update the configuration with custom values.

    Dict-valued keys (e.g. ``data_vendors``) are merged one level deep so a
    partial update like ``{"data_vendors": {"core_stock_apis": "alpha_vantage"}}``
    keeps the other nested keys from the default; scalar keys are replaced.
    """
    global _config
    initialize_config(force=False)
    if _config is None:
        _config = {}
    current_config = _config
    incoming = deepcopy(config)
    for key, value in incoming.items():
        if isinstance(value, dict) and isinstance(current_config.get(key), dict):
            current_value = current_config[key]
            if isinstance(current_value, dict):
                current_value.update(value)
        else:
            current_config[key] = value
    _ensure_data_dir_structure(current_config.get("data_dir"))


def get_config() -> Dict:
    """Get the current configuration."""
    if _config is None:
        initialize_config()
    return deepcopy(_config or {})


def _ensure_data_dir_structure(data_dir: Optional[str]) -> None:
    if not data_dir:
        return
    base = Path(data_dir).expanduser()
    for relative in (
        "finnhub",
        "finnhub/news",
        "finnhub/insider_sentiment",
        "finnhub/insider_transactions",
        "finnhub_data/news_data",
    ):
        (base / relative).mkdir(parents=True, exist_ok=True)


def get_data_dir() -> str:
    """Return the configured data directory, honoring env overrides."""
    cfg = get_config()
    data_dir = os.getenv("TRADING_AGENTS_DATA_DIR") or cfg.get("data_dir")
    if not data_dir:
        project_dir = cfg.get("project_dir") or os.getcwd()
        data_dir = str(Path(project_dir) / "data")
        set_config({"data_dir": data_dir})
    _ensure_data_dir_structure(data_dir)
    return data_dir


def set_data_dir(data_dir: str) -> None:
    """Set and create the data directory used by legacy dataflow scripts."""
    set_config({"data_dir": str(Path(data_dir).expanduser())})


# Initialize with default config
initialize_config()
