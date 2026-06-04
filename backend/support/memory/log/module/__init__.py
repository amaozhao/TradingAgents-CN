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
    ),
    package="support.memory.log.module",
    logical_file=str(_ROOT / "backend/support/memory/log/module.py"),
)
del _Path, _ROOT, _execute, _parent
