#!/usr/bin/env python3
"""Audit source and test naming rules for the repository cleanup plan."""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Literal


ROOT = Path(__file__).resolve().parents[1]

SOURCE_ROOTS = (
    Path("backend/app"),
    Path("backend/tradingagents"),
    Path("backend/cli"),
)
BACKEND_TEST_ROOT = Path("backend/tests")
MAGIC_PYTHON_FILES = {"__init__.py", "__main__.py", "conftest.py"}
SKIP_DIR_NAMES = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "dist",
    "node_modules",
    "runtime",
}
SKIP_SUBTREES = (
    Path("backend/tradingagents/dataflows/cache/data_cache"),
)

PYTHON_EXTENSIONS = {".py"}
SCANNED_EXTENSIONS = PYTHON_EXTENSIONS

RecordKind = Literal["source", "test", "magic", "generated", "directory"]


@dataclass(frozen=True)
class AuditRecord:
    path: str
    kind: RecordKind
    current_basename: str
    proposed_basename: str
    violates_name: bool
    proposed_collision: bool
    mirror_valid: bool | None
    collision_key: str
    reasons: list[str]


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _iter_paths() -> Iterable[Path]:
    scan_roots = (
        Path("backend/app"),
        Path("backend/tradingagents"),
        Path("backend/cli"),
        Path("backend/tests"),
    )
    for root in scan_roots:
        absolute = ROOT / root
        if not absolute.exists():
            continue
        for path in absolute.rglob("*"):
            rel = path.relative_to(ROOT)
            if any(part in SKIP_DIR_NAMES for part in rel.parts):
                continue
            if any(_is_relative_to(rel, skipped) for skipped in SKIP_SUBTREES):
                continue
            yield rel


def _is_test_file(path: Path) -> bool:
    if _is_relative_to(path, BACKEND_TEST_ROOT) and path.suffix == ".py":
        return True
    return False


def _is_source_file(path: Path) -> bool:
    if path.suffix not in SCANNED_EXTENSIONS:
        return False
    return any(_is_relative_to(path, root) for root in SOURCE_ROOTS)


def _normalize_stem(stem: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9]+", "", stem)
    return normalized.lower()


def _single_word_stem(stem: str) -> bool:
    return bool(re.fullmatch(r"[a-z0-9]+", stem))


def _directory_is_single_word(name: str) -> bool:
    return bool(re.fullmatch(r"[a-z0-9]+", name))


def _proposed_source_name(path: Path) -> str:
    return f"{_normalize_stem(path.stem)}{path.suffix.lower()}"


def _proposed_test_name(path: Path) -> str:
    suffix = path.suffix.lower()
    stem = path.stem
    if stem.endswith(".test"):
        stem = stem.removesuffix(".test")
    if stem.startswith("test_"):
        stem = stem.removeprefix("test_")
    elif stem.startswith("test"):
        stem = stem.removeprefix("test")
    source_stem = _normalize_stem(stem)
    return f"test_{source_stem}{suffix}"


def _expected_backend_source_for_test(path: Path) -> Path | None:
    try:
        rel = path.relative_to(BACKEND_TEST_ROOT)
    except ValueError:
        return None
    if not rel.parts:
        return None
    top = rel.parts[0]
    if top not in {"app", "tradingagents", "cli"}:
        return None
    if not path.name.startswith("test_"):
        return None
    source_name = path.name.removeprefix("test_")
    return Path("backend") / rel.parent / source_name


def _mirror_valid(path: Path) -> bool:
    if _is_relative_to(path, BACKEND_TEST_ROOT):
        expected = _expected_backend_source_for_test(path)
        return expected is not None and (ROOT / expected).exists()
    return False


def _record_file(path: Path) -> AuditRecord | None:
    if path.suffix not in SCANNED_EXTENSIONS:
        return None

    reasons: list[str] = []
    mirror: bool | None = None

    if path.name in MAGIC_PYTHON_FILES:
        kind: RecordKind = "magic"
        proposed = path.name
        violates = False
        collision_key = ""
    elif _is_test_file(path):
        kind = "test"
        proposed = _proposed_test_name(path)
        mirror = _mirror_valid(path)
        violates = path.name != proposed
        collision_key = f"test:{proposed}"
        if violates:
            reasons.append("test file must be named test_<source_stem>")
        if not mirror:
            reasons.append("test file does not mirror an existing source file")
    elif _is_source_file(path):
        kind = "source"
        proposed = _proposed_source_name(path)
        violates = path.name != proposed or not _single_word_stem(path.stem)
        collision_key = f"source:{proposed}"
        if violates:
            reasons.append("source file must be one lowercase word")
    else:
        return None

    return AuditRecord(
        path=path.as_posix(),
        kind=kind,
        current_basename=path.name,
        proposed_basename=proposed,
        violates_name=violates,
        proposed_collision=False,
        mirror_valid=mirror,
        collision_key=collision_key,
        reasons=reasons,
    )


def _record_directory(path: Path) -> AuditRecord | None:
    if not (ROOT / path).is_dir():
        return None
    if path.name in SKIP_DIR_NAMES:
        return None
    if path.name in {"app", "tradingagents", "cli", "tests", "src", "frontend", "backend"}:
        return None

    proposed = _normalize_stem(path.name)
    violates = path.name != proposed or not _directory_is_single_word(path.name)
    reasons = ["directory must be one lowercase word"] if violates else []
    return AuditRecord(
        path=path.as_posix(),
        kind="directory",
        current_basename=path.name,
        proposed_basename=proposed,
        violates_name=violates,
        proposed_collision=False,
        mirror_valid=None,
        collision_key=f"directory:{proposed}",
        reasons=reasons,
    )


def collect_records() -> list[AuditRecord]:
    records: list[AuditRecord] = []
    for path in _iter_paths():
        if (ROOT / path).is_dir():
            record = _record_directory(path)
        else:
            record = _record_file(path)
        if record is not None:
            records.append(record)

    collision_groups: dict[str, list[int]] = defaultdict(list)
    for index, record in enumerate(records):
        if record.kind in {"source", "test"} and record.collision_key:
            collision_groups[record.collision_key].append(index)

    mutable = [asdict(record) for record in records]
    for indexes in collision_groups.values():
        if len(indexes) < 2:
            continue
        for index in indexes:
            mutable[index]["proposed_collision"] = True
            mutable[index]["reasons"].append("proposed name collides with another in-scope item")

    return [AuditRecord(**item) for item in mutable]


def _summary(records: list[AuditRecord]) -> dict[str, int]:
    return {
        "total": len(records),
        "sources": sum(record.kind == "source" for record in records),
        "tests": sum(record.kind == "test" for record in records),
        "directories": sum(record.kind == "directory" for record in records),
        "name_violations": sum(record.violates_name for record in records),
        "collisions": sum(record.proposed_collision for record in records),
        "mirror_violations": sum(record.kind == "test" and record.mirror_valid is False for record in records),
    }


def _to_json(records: list[AuditRecord]) -> str:
    payload = {
        "summary": _summary(records),
        "records": [asdict(record) for record in records],
    }
    return json.dumps(payload, indent=2, ensure_ascii=False)


def _to_markdown(records: list[AuditRecord]) -> str:
    summary = _summary(records)
    lines = [
        "# Naming Audit Baseline",
        "",
        "## Summary",
        "",
    ]
    for key, value in summary.items():
        lines.append(f"- {key}: {value}")

    problem_records = [
        record
        for record in records
        if record.violates_name or record.proposed_collision or record.mirror_valid is False
    ]
    lines.extend(["", "## Problems", ""])
    if not problem_records:
        lines.append("No naming, collision, or mirror violations found.")
    else:
        lines.append("| kind | path | current | proposed | reasons |")
        lines.append("| --- | --- | --- | --- | --- |")
        for record in sorted(problem_records, key=lambda item: (item.kind, item.path)):
            reasons = "; ".join(record.reasons)
            lines.append(
                f"| {record.kind} | `{record.path}` | `{record.current_basename}` | "
                f"`{record.proposed_basename}` | {reasons} |"
            )

    collision_groups: dict[str, list[AuditRecord]] = defaultdict(list)
    for record in records:
        if record.proposed_collision:
            collision_groups[record.collision_key].append(record)
    lines.extend(["", "## Collision Groups", ""])
    if not collision_groups:
        lines.append("No proposed-name collisions found.")
    else:
        for key, group in sorted(collision_groups.items()):
            lines.append(f"### `{key}`")
            for record in sorted(group, key=lambda item: item.path):
                lines.append(f"- `{record.path}`")
            lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _write_or_print(text: str, output: str | None) -> None:
    if output:
        output_path = ROOT / output
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(text, encoding="utf-8")
        return
    print(text, end="")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--format", choices=("json", "markdown"), default="markdown")
    parser.add_argument("--output")
    parser.add_argument("--check", action="store_true", help="Exit non-zero when any violation is present.")
    args = parser.parse_args()

    records = collect_records()
    text = _to_json(records) if args.format == "json" else _to_markdown(records)
    _write_or_print(text, args.output)

    summary = _summary(records)
    if args.check and (
        summary["name_violations"] or summary["collisions"] or summary["mirror_violations"]
    ):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
