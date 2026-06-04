from pathlib import Path as _Path

from support.loader import execute as _execute

_ROOT = _Path(__file__).resolve()
for _parent in (_ROOT, *_ROOT.parents):
    if (_parent / "backend" / "pyproject.toml").is_file():
        _ROOT = _parent
        break

_execute(
    globals(),
    __file__,
    (
        "imports.py",
        "common.py",
        "base.py",
        "models.py",
        "query.py",
        "service.py",
        "task.py",
        "route.py",
        "status.py",
        "report.py",
        "cache.py",
        "sync.py",
        "flow.py",
        "data.py",
        "provider.py",
        "helper.py",
        "runtime.py",
        "summary.py",
    ),
    package="trader.flows.china",
    logical_file=str(_ROOT / "backend/trader/flows/china.py"),
)
del _Path, _ROOT, _execute, _parent
