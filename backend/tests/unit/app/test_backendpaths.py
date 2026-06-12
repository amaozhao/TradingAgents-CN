from __future__ import annotations

import re
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[3]
BACKEND_CODE_ROOTS = ("app", "cli", "scripts", "trader", "tests")
ALLOWED_DUNDER_FILES = {"__init__.py", "__main__.py"}
IGNORED_PARTS = {
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    "data",
    "data_cache",
    "dataflows",
    "runtime",
}
SINGLE_WORD_RE = re.compile(r"^[A-Za-z0-9]+(?:\.[A-Za-z0-9]+)?$")
GLUED_MULTIWORD_NAMES = {
    "alphazoo",
    "baostockruntime",
    "benchrunner",
    "comparerunner",
    "factoranalysiscore",
    "marketdata",
    "marketseries",
    "multifactor",
    "networkproxy",
    "panelloader",
    "providerclient",
    "researchagent",
    "researchmatrix",
    "usermodelkeys",
}


def _is_ignored(path: Path) -> bool:
    relative = path.relative_to(BACKEND_ROOT)
    return any(part in IGNORED_PARTS for part in relative.parts)


def _singleword_path_violations() -> list[str]:
    violations: list[str] = []
    for root_name in BACKEND_CODE_ROOTS:
        root = BACKEND_ROOT / root_name
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if _is_ignored(path):
                continue
            name = path.name
            if path.is_file() and name in ALLOWED_DUNDER_FILES:
                continue
            if path.is_file() and name.endswith((".pyc", ".pyo")):
                continue
            stem = name.rsplit(".", 1)[0]
            if (
                not SINGLE_WORD_RE.fullmatch(name)
                or stem.lower() in GLUED_MULTIWORD_NAMES
            ):
                violations.append(str(path.relative_to(BACKEND_ROOT)))
    return sorted(violations)


def test_backend_code_path_audit_has_actionable_findings():
    violations = _singleword_path_violations()

    assert "app/services/alpha_zoo" in violations
    assert all(str(path).startswith(BACKEND_CODE_ROOTS) for path in violations)
