#!/usr/bin/env python3
"""Audit backend Python filenames for the single-word naming rule."""

from __future__ import annotations

import argparse
import ast
import json
import re
import tokenize
from dataclasses import asdict, dataclass
from functools import lru_cache
from io import StringIO
from pathlib import Path
from typing import Iterable, Literal


ROOT = Path(__file__).resolve().parents[1]

BACKEND_ROOT = Path("backend")
TEST_ROOTS = (
    Path("backend/tests"),
    Path("backend/support"),
)
TEST_MIRROR_ROOTS = {
    Path("backend/tests/app"): Path("backend/app"),
    Path("backend/tests/cli"): Path("backend/cli"),
    Path("backend/tests/trader"): Path("backend/trader"),
}

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
    Path("backend/trader/flows/cache/data/cache"),
)

DB_SINGULAR_MODULES = {
    "accounts": "account",
    "documents": "document",
    "messages": "message",
    "models": "model",
    "operations": "operation",
    "preferences": "preference",
    "stocks": "stock",
    "writes": "write",
}
SERVICE_SINGULAR_MODULES = {
    "backups": "backup",
    "basics": "basic",
    "capabilities": "capability",
    "exports": "export",
    "favorites": "favorite",
    "helpers": "helper",
    "keys": "key",
    "logs": "log",
    "messages": "message",
    "notifications": "notification",
    "operations": "operation",
    "sources": "source",
    "tags": "tag",
    "users": "user",
    "utils": "util",
}
FORBIDDEN_SERVICE_DIRS = {
    Path("backend/app/services/data"): Path("backend/app/services/market"),
}
FORBIDDEN_SERVICE_FILES = {
    Path("backend/app/services/stocks/data.py"): Path("backend/app/services/stocks/service.py"),
}
GLUED_TRADING_AGENTS = "trading" + "agents"
GLUED_TRADING_AGENTS_RUNTIME_SETTINGS = GLUED_TRADING_AGENTS + "runtimesettings"
GLUED_TEST_SUPPORT = "test" + "support"
GLUED_DATA_FLOWS = "data" + "flows"
GLUED_LLM_CLIENTS = "llm" + "clients"
GLUED_LLM_ADAPTERS = "llm" + "adapters"
SNAKE_LLM_CLIENTS = "llm" + "_" + "clients"
SNAKE_LLM_ADAPTERS = "llm" + "_" + "adapters"
GLUED_RISK_MANAGEMENT = "risk" + "mgmt"
SNAKE_RISK_MANAGEMENT = "risk" + "_" + "mgmt"
GLUED_PYPANDOC_FUNCTIONALITY = "pypandoc" + "functionality"
FORBIDDEN_DIRECTORIES = {
    Path("backend") / GLUED_TEST_SUPPORT: Path("backend/support"),
    Path("backend") / GLUED_TRADING_AGENTS: Path("backend/trader"),
    Path("backend/trader") / GLUED_DATA_FLOWS: Path("backend/trader/flows"),
    Path("backend/trader") / GLUED_LLM_CLIENTS: Path("backend/trader/llm/clients"),
    Path("backend/trader") / SNAKE_LLM_CLIENTS: Path("backend/trader/llm/clients"),
    Path("backend/trader") / GLUED_LLM_ADAPTERS: Path("backend/trader/llm/adapters"),
    Path("backend/trader") / SNAKE_LLM_ADAPTERS: Path("backend/trader/llm/adapters"),
    Path("backend/trader/agents") / GLUED_RISK_MANAGEMENT: Path("backend/trader/agents/risk/management"),
    Path("backend/trader/agents") / SNAKE_RISK_MANAGEMENT: Path("backend/trader/agents/risk/management"),
    Path("backend/tests/trader") / GLUED_DATA_FLOWS: Path("backend/tests/trader/flows"),
    Path("backend/tests/trader") / GLUED_LLM_CLIENTS: Path("backend/tests/trader/llm/clients"),
    Path("backend/tests/trader") / GLUED_LLM_ADAPTERS: Path("backend/tests/trader/llm/adapters"),
    Path("backend/support") / GLUED_TRADING_AGENTS: Path("backend/support/trading/agents"),
    Path("backend/support") / GLUED_TRADING_AGENTS_RUNTIME_SETTINGS: Path("backend/support/trading/agents/runtime/settings"),
    Path("backend/support") / GLUED_PYPANDOC_FUNCTIONALITY: Path("backend/support/pypandoc/functionality"),
}
FORBIDDEN_FILES = {
    Path("backend/web/components/operations.py"): Path("backend/web/components/operation.py"),
    Path("backend/web/components/results.py"): Path("backend/web/components/result.py"),
}
ALLOWED_CAMELCASE_IDENTIFIERS = {
    "TradingAgentsGraph",
    "TradingAgentsLogger",
}
ALLOWED_NON_SNAKE_NAMES = {
    "_",
    "self",
    "cls",
}

# This is not a dictionary of English. It is the repo vocabulary used to
# distinguish approved one-word module names from glued code concepts such as
# "stockapiendpoint" or "defaultconfig".
KNOWN_CODE_WORDS = {
    "account",
    "accounts",
    "activity",
    "adapter",
    "adaptive",
    "aggressive",
    "ai",
    "akshare",
    "alpha",
    "analysis",
    "analyst",
    "analysts",
    "anthropic",
    "api",
    "app",
    "async",
    "auth",
    "azure",
    "backup",
    "backups",
    "baostock",
    "base",
    "basics",
    "bear",
    "bridge",
    "bull",
    "cache",
    "capabilities",
    "catalog",
    "checker",
    "checkpointer",
    "china",
    "chroma",
    "cleanup",
    "client",
    "common",
    "compat",
    "completeness",
    "conditions",
    "config",
    "conservative",
    "consistency",
    "context",
    "cookies",
    "core",
    "data",
    "database",
    "databases",
    "dataframe",
    "db",
    "deepseek",
    "default",
    "dev",
    "docker",
    "document",
    "documents",
    "dual",
    "endpoint",
    "enhanced",
    "env",
    "error",
    "errors",
    "eval",
    "examples",
    "execution",
    "export",
    "exports",
    "factory",
    "favorite",
    "favorites",
    "file",
    "files",
    "filter",
    "financial",
    "finnhub",
    "flow",
    "flows",
    "foreign",
    "form",
    "frame",
    "fundamental",
    "fundamentals",
    "google",
    "graph",
    "handler",
    "header",
    "health",
    "helpers",
    "historical",
    "hk",
    "improved",
    "indicator",
    "indicators",
    "ingestion",
    "init",
    "instrument",
    "instruments",
    "integrated",
    "integration",
    "interface",
    "key",
    "keys",
    "legacy",
    "limiter",
    "limits",
    "log",
    "logging",
    "login",
    "logs",
    "main",
    "manager",
    "market",
    "markets",
    "media",
    "memory",
    "message",
    "messages",
    "metrics",
    "migrate",
    "middleware",
    "model",
    "models",
    "mongo",
    "mongodb",
    "multi",
    "native",
    "neutral",
    "news",
    "notification",
    "notifications",
    "openai",
    "operation",
    "operations",
    "optimized",
    "paper",
    "periods",
    "persistence",
    "portfolio",
    "postgres",
    "preference",
    "preferences",
    "processing",
    "progress",
    "propagation",
    "provider",
    "providers",
    "query",
    "queue",
    "quote",
    "quotes",
    "rate",
    "rating",
    "realtime",
    "reddit",
    "redis",
    "reflection",
    "report",
    "reports",
    "repository",
    "request",
    "requests",
    "research",
    "response",
    "results",
    "risk",
    "risky",
    "router",
    "run",
    "runtime",
    "scheduler",
    "schemas",
    "screen",
    "screening",
    "sdk",
    "sentiment",
    "serialization",
    "service",
    "session",
    "sessions",
    "setup",
    "sidebar",
    "signal",
    "signals",
    "simple",
    "smart",
    "social",
    "socket",
    "source",
    "sources",
    "sse",
    "startup",
    "states",
    "stats",
    "status",
    "stock",
    "stocks",
    "stocktwits",
    "structured",
    "symbols",
    "sync",
    "system",
    "tag",
    "tags",
    "test",
    "threads",
    "timezone",
    "tokens",
    "tool",
    "tools",
    "tracker",
    "trade",
    "trader",
    "trading",
    "tushare",
    "ui",
    "unified",
    "us",
    "usage",
    "user",
    "users",
    "utils",
    "validation",
    "validator",
    "validators",
    "vantage",
    "websocket",
    "worker",
    "writes",
    "yfinance",
}
KNOWN_CODE_WORDS.update(
    {
        "adapter",
        "adapters",
        "advice",
        "all",
        "amount",
        "asyncx",
        "backfill",
        "binding",
        "calling",
        "checkpoint",
        "clients",
        "codes",
        "coercion",
        "comparison",
        "complete",
        "crypto",
        "cutover",
        "daily",
        "dashscope",
        "date",
        "deduplication",
        "delete",
        "depth",
        "detailed",
        "display",
        "docs",
        "documentation",
        "duplicate",
        "ed",
        "embedding",
        "estimation",
        "fi",
        "field",
        "fields",
        "filtering",
        "final",
        "friendly",
        "functionality",
        "generation",
        "hkstock",
        "identification",
        "imports",
        "industries",
        "integrity",
        "interception",
        "inventory",
        "investment",
        "issue",
        "llm",
        "management",
        "mapping",
        "metrics",
        "naming",
        "no",
        "openapi",
        "optimization",
        "pandoc",
        "pb",
        "pypandoc",
        "react",
        "reasoning",
        "removal",
        "resume",
        "safe",
        "scenario",
        "skip",
        "steps",
        "symbol",
        "thread",
        "ticket",
        "ticker",
        "timezone",
        "token",
        "volume",
        "workflow",
    }
)

RecordKind = Literal["source", "test", "magic"]


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


def _iter_files() -> Iterable[Path]:
    absolute = ROOT / BACKEND_ROOT
    if not absolute.exists():
        return

    for path in absolute.rglob("*.py"):
        rel = path.relative_to(ROOT)
        if any(part in SKIP_DIR_NAMES for part in rel.parts):
            continue
        if any(_is_relative_to(rel, skipped) for skipped in SKIP_SUBTREES):
            continue
        yield rel


def _single_word_shape(stem: str) -> bool:
    return bool(re.fullmatch(r"[a-z][a-z0-9]*", stem))


@lru_cache(maxsize=None)
def _known_word_split(stem: str) -> tuple[str, ...] | None:
    if not stem:
        return ()

    for end in range(1, len(stem) + 1):
        prefix = stem[:end]
        if prefix not in KNOWN_CODE_WORDS:
            continue
        suffix = _known_word_split(stem[end:])
        if suffix is not None:
            return (prefix, *suffix)

    return None


def _glued_compound_parts(stem: str) -> tuple[str, ...] | None:
    if stem in KNOWN_CODE_WORDS:
        return None

    parts = _known_word_split(stem)
    if parts is not None and len(parts) > 1:
        return parts
    return None


def _validate_single_word_stem(stem: str) -> list[str]:
    reasons: list[str] = []
    if not _single_word_shape(stem):
        reasons.append("filename stem must be one lowercase word without separators")
        return reasons

    glued = _glued_compound_parts(stem)
    if glued is not None:
        reasons.append(f"filename stem is glued compound words: {' + '.join(glued)}")

    return reasons


def _validate_directory_parts(path: Path) -> list[str]:
    reasons: list[str] = []
    for part in path.parent.parts:
        if part == "backend" or part in SKIP_DIR_NAMES:
            continue
        part_reasons = _validate_single_word_stem(part)
        for reason in part_reasons:
            reasons.append(f"directory segment `{part}`: {reason}")
    return reasons


def _validate_python_identifiers(path: Path) -> list[str]:
    absolute = ROOT / path
    try:
        source = absolute.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        source = absolute.read_text(encoding="utf-8-sig")

    violations: list[str] = []
    seen: set[str] = set()
    try:
        tokens = tokenize.generate_tokens(StringIO(source).readline)
        for token in tokens:
            if token.type != tokenize.NAME:
                continue
            identifier = token.string
            if identifier in ALLOWED_CAMELCASE_IDENTIFIERS:
                continue
            if GLUED_TRADING_AGENTS in identifier.lower():
                seen.add(identifier)
    except tokenize.TokenError as exc:
        violations.append(f"could not tokenize Python identifiers: {exc}")

    for identifier in sorted(seen):
        violations.append(
            f"identifier `{identifier}` is glued compound words; use snake_case for variables/functions or CamelCase for types"
        )
    return violations


def _is_dunder_name(name: str) -> bool:
    return len(name) > 4 and name.startswith("__") and name.endswith("__")


def _is_snake_name(name: str) -> bool:
    if name in ALLOWED_NON_SNAKE_NAMES or _is_dunder_name(name):
        return True
    return bool(re.fullmatch(r"_*[a-z][a-z0-9]*(?:_[a-z0-9]+)*_*", name))


def _is_upper_snake_name(name: str) -> bool:
    return bool(re.fullmatch(r"_*[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)*_*", name))


def _is_pascal_name(name: str) -> bool:
    return bool(re.fullmatch(r"_*[A-Z][A-Za-z0-9]*", name))


def _is_framework_method_name(name: str) -> bool:
    if name in {"setUp", "tearDown", "setUpClass", "tearDownClass"}:
        return True
    return bool(re.fullmatch(r"visit_[A-Z][A-Za-z0-9]*", name))


def _is_value_bound_to_type(value: ast.AST | None) -> bool:
    if isinstance(value, ast.Name):
        return _is_pascal_name(value.id)
    if isinstance(value, ast.Attribute):
        return _is_pascal_name(value.attr)
    if isinstance(value, ast.Subscript):
        return _is_value_bound_to_type(value.value)
    if isinstance(value, ast.Call):
        return _is_value_bound_to_type(value.func)
    return False


def _target_names(target: ast.AST) -> Iterable[tuple[str, int, str]]:
    if isinstance(target, ast.Name):
        yield target.id, target.lineno, "variable"
    elif isinstance(target, ast.Starred):
        yield from _target_names(target.value)
    elif isinstance(target, (ast.Tuple, ast.List)):
        for item in target.elts:
            yield from _target_names(item)
    elif isinstance(target, ast.Attribute):
        if isinstance(target.value, ast.Name) and target.value.id in {"self", "cls"}:
            yield target.attr, target.lineno, f"{target.value.id} attribute"


class _IdentifierStyleVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.violations: list[str] = []

    def _add(self, lineno: int, kind: str, name: str, expectation: str) -> None:
        self.violations.append(f"line {lineno}: {kind} `{name}` must be {expectation}")

    def _check_snake_or_constant(self, lineno: int, kind: str, name: str) -> None:
        if _is_snake_name(name) or _is_upper_snake_name(name):
            return
        self._add(lineno, kind, name, "snake_case or UPPER_SNAKE_CASE")

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        if node.name not in ALLOWED_CAMELCASE_IDENTIFIERS and not _is_pascal_name(node.name):
            self._add(node.lineno, "type", node.name, "PascalCase")
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_function(node)

    def _visit_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        if not _is_snake_name(node.name) and not _is_framework_method_name(node.name):
            self._add(node.lineno, "function/method", node.name, "snake_case")
        for arg in (
            list(node.args.posonlyargs)
            + list(node.args.args)
            + list(node.args.kwonlyargs)
        ):
            self._check_snake_or_constant(arg.lineno, "argument", arg.arg)
        if node.args.vararg is not None:
            self._check_snake_or_constant(node.args.vararg.lineno, "argument", node.args.vararg.arg)
        if node.args.kwarg is not None:
            self._check_snake_or_constant(node.args.kwarg.lineno, "argument", node.args.kwarg.arg)
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:
        for target in node.targets:
            for name, lineno, kind in _target_names(target):
                if _is_pascal_name(name):
                    continue
                if _is_value_bound_to_type(node.value) and _is_pascal_name(name):
                    continue
                self._check_snake_or_constant(lineno, kind, name)
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        for name, lineno, kind in _target_names(node.target):
            if _is_pascal_name(name):
                continue
            if _is_value_bound_to_type(node.annotation) and _is_pascal_name(name):
                continue
            if _is_value_bound_to_type(node.value) and _is_pascal_name(name):
                continue
            self._check_snake_or_constant(lineno, kind, name)
        self.generic_visit(node)

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        for name, lineno, kind in _target_names(node.target):
            self._check_snake_or_constant(lineno, kind, name)
        self.generic_visit(node)

    def visit_For(self, node: ast.For) -> None:
        for name, lineno, kind in _target_names(node.target):
            self._check_snake_or_constant(lineno, kind, name)
        self.generic_visit(node)

    def visit_AsyncFor(self, node: ast.AsyncFor) -> None:
        for name, lineno, kind in _target_names(node.target):
            self._check_snake_or_constant(lineno, kind, name)
        self.generic_visit(node)

    def visit_With(self, node: ast.With) -> None:
        for item in node.items:
            if item.optional_vars is None:
                continue
            for name, lineno, kind in _target_names(item.optional_vars):
                self._check_snake_or_constant(lineno, kind, name)
        self.generic_visit(node)

    def visit_AsyncWith(self, node: ast.AsyncWith) -> None:
        for item in node.items:
            if item.optional_vars is None:
                continue
            for name, lineno, kind in _target_names(item.optional_vars):
                self._check_snake_or_constant(lineno, kind, name)
        self.generic_visit(node)

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        if node.name:
            self._check_snake_or_constant(node.lineno, "exception variable", node.name)
        self.generic_visit(node)

    def visit_NamedExpr(self, node: ast.NamedExpr) -> None:
        for name, lineno, kind in _target_names(node.target):
            self._check_snake_or_constant(lineno, kind, name)
        self.generic_visit(node)


def _validate_python_identifier_styles(path: Path) -> list[str]:
    absolute = ROOT / path
    try:
        source = absolute.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        source = absolute.read_text(encoding="utf-8-sig")

    try:
        tree = ast.parse(source, filename=path.as_posix())
    except SyntaxError as exc:
        return [f"could not parse Python identifiers: {exc}"]

    visitor = _IdentifierStyleVisitor()
    visitor.visit(tree)
    return visitor.violations


def _record_file(path: Path) -> AuditRecord:
    directory_reasons: list[str] = []
    directory_proposed = path.name
    for forbidden, replacement in FORBIDDEN_DIRECTORIES.items():
        if _is_relative_to(path, forbidden):
            directory_reasons.append(
                f"directory {forbidden.as_posix()} is a glued compound name; use {replacement.as_posix()}"
            )
            directory_proposed = replacement.name

    if path.name in MAGIC_PYTHON_FILES:
        directory_reasons.extend(_validate_directory_parts(path))
        return AuditRecord(
            path=path.as_posix(),
            kind="magic",
            current_basename=path.name,
            proposed_basename=directory_proposed,
            violates_name=bool(directory_reasons),
            proposed_collision=False,
            mirror_valid=None,
            collision_key="",
            reasons=directory_reasons,
        )

    kind: RecordKind = "test" if any(_is_relative_to(path, root) for root in TEST_ROOTS) else "source"
    stem = path.stem
    reasons: list[str]

    reasons = [
        *directory_reasons,
        *_validate_directory_parts(path),
        *_validate_single_word_stem(stem),
        *_validate_python_identifiers(path),
        *_validate_python_identifier_styles(path),
    ]
    proposed_basename = "<move context into directories; choose one word>.py" if reasons else path.name
    if directory_reasons:
        proposed_basename = directory_proposed
    mirror_valid: bool | None = None
    if path.parent == Path("backend/app/db") and stem in DB_SINGULAR_MODULES:
        reasons.append(
            f"db module filenames use singular domain nouns; use {DB_SINGULAR_MODULES[stem]}.py"
        )
        proposed_basename = f"{DB_SINGULAR_MODULES[stem]}.py"
    if _is_relative_to(path, Path("backend/app/services")) and stem in SERVICE_SINGULAR_MODULES:
        reasons.append(
            f"service module filenames use singular domain nouns; use {SERVICE_SINGULAR_MODULES[stem]}.py"
        )
        proposed_basename = f"{SERVICE_SINGULAR_MODULES[stem]}.py"
    for forbidden, replacement in FORBIDDEN_SERVICE_DIRS.items():
        if _is_relative_to(path, forbidden):
            reasons.append(
                f"service source directory {forbidden.as_posix()} is ignored; use {replacement.as_posix()}"
            )
            proposed_basename = replacement.name
    if path in FORBIDDEN_SERVICE_FILES:
        replacement = FORBIDDEN_SERVICE_FILES[path]
        reasons.append(
            f"service source file {path.as_posix()} is too generic; use {replacement.as_posix()}"
        )
        proposed_basename = replacement.name
    if path in FORBIDDEN_FILES:
        replacement = FORBIDDEN_FILES[path]
        reasons.append(f"source file {path.as_posix()} is forbidden; use {replacement.as_posix()}")
        proposed_basename = replacement.name
    if path.name == "test.py":
        for test_root, source_root in TEST_MIRROR_ROOTS.items():
            if not _is_relative_to(path, test_root):
                continue
            source_path = source_root / path.relative_to(test_root).parent
            source_path = source_path.with_suffix(".py")
            mirror_valid = (ROOT / source_path).exists()
            if not mirror_valid:
                reasons.append(
                    f"test path must mirror an existing source file; expected {source_path.as_posix()}"
                )
            break

    return AuditRecord(
        path=path.as_posix(),
        kind=kind,
        current_basename=path.name,
        proposed_basename=proposed_basename,
        violates_name=bool(reasons),
        proposed_collision=False,
        mirror_valid=mirror_valid,
        collision_key="",
        reasons=reasons,
    )


def collect_records(*, include_tests: bool = False) -> list[AuditRecord]:
    return [_record_file(path) for path in _iter_files()]


def _summary(records: list[AuditRecord]) -> dict[str, int]:
    return {
        "total": len(records),
        "sources": sum(record.kind == "source" for record in records),
        "tests": sum(record.kind == "test" for record in records),
        "magic": sum(record.kind == "magic" for record in records),
        "name_violations": sum(record.violates_name for record in records),
        "collisions": 0,
        "mirror_violations": sum(record.mirror_valid is False for record in records),
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
        "# Naming Audit",
        "",
        "## Summary",
        "",
    ]
    for key, value in summary.items():
        lines.append(f"- {key}: {value}")

    problem_records = [record for record in records if record.violates_name or record.mirror_valid is False]
    lines.extend(["", "## Problems", ""])
    if not problem_records:
        lines.append("No naming violations found.")
    else:
        lines.append("| kind | path | current | guidance | reasons |")
        lines.append("| --- | --- | --- | --- | --- |")
        for record in sorted(problem_records, key=lambda item: (item.kind, item.path)):
            reasons = "; ".join(record.reasons)
            lines.append(
                f"| {record.kind} | `{record.path}` | `{record.current_basename}` | "
                f"`{record.proposed_basename}` | {reasons} |"
            )

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
    parser.add_argument(
        "--include-tests",
        action="store_true",
        help="Compatibility flag; all backend Python files are always scanned.",
    )
    args = parser.parse_args()

    records = collect_records(include_tests=args.include_tests)
    text = _to_json(records) if args.format == "json" else _to_markdown(records)
    _write_or_print(text, args.output)

    summary = _summary(records)
    if args.check and (summary["name_violations"] or summary["mirror_violations"]):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
