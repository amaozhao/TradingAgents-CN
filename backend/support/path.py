from pathlib import Path


def _find_backend_root(start: Path) -> Path:
    for parent in (start, *start.parents):
        if (parent / "pyproject.toml").is_file() and (parent / "app").is_dir():
            return parent
    return start


BACKEND_ROOT = _find_backend_root(Path(__file__).resolve())
REPO_ROOT = BACKEND_ROOT.parent
