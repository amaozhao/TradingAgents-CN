from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
from typing import Any

HTTP_DECORATORS = {"get", "post", "put", "patch", "delete"}
MONGO_IMPORT_MODULES = {
    "app.core.coredatabase",
    "pymongo",
    "motor",
    "motor.motor_asyncio",
}
MONGO_HELPERS = {"get_mongo_db", "get_mongo_db_sync", "get_database"}
MONGO_WRITE_METHODS = {
    "insert_one",
    "insert_many",
    "update_one",
    "update_many",
    "replace_one",
    "delete_one",
    "delete_many",
    "bulk_write",
}


def scan_backend(root: str | Path, output_path: str | Path | None = None) -> dict[str, Any]:
    root_path = Path(root)
    scan_root = root_path / "app" if (root_path / "app").is_dir() else root_path
    files = sorted(_iter_python_files(scan_root))

    contracts: list[dict[str, Any]] = []
    missing_response_models: list[dict[str, Any]] = []
    raw_request_bodies: list[dict[str, Any]] = []
    mongo_access: list[dict[str, Any]] = []
    mongo_writes: list[dict[str, Any]] = []

    for file_path in files:
        try:
            tree = ast.parse(file_path.read_text(encoding="utf-8"), filename=str(file_path))
        except SyntaxError as exc:
            mongo_access.append(
                {
                    "path": _rel(file_path, root_path),
                    "kind": "parse_error",
                    "line": exc.lineno or 0,
                    "detail": str(exc),
                }
            )
            continue

        rel_path = _rel(file_path, root_path)
        visitor = _InventoryVisitor(rel_path)
        visitor.visit(tree)
        contracts.extend(visitor.contracts)
        missing_response_models.extend(visitor.missing_response_models)
        raw_request_bodies.extend(visitor.raw_request_bodies)
        mongo_access.extend(visitor.mongo_access)
        mongo_writes.extend(visitor.mongo_writes)

    worker_write_files = {
        item["path"]
        for item in mongo_writes
        if item["path"].startswith("app/worker/") or item["path"] == "app/worker.py"
    }
    inventory = {
        "summary": {
            "python_files_scanned": len(files),
            "response_model_dict_endpoints": len(contracts),
            "missing_response_model_endpoints": len(missing_response_models),
            "raw_dict_request_bodies": len(raw_request_bodies),
            "mongo_access_files": len({item["path"] for item in mongo_access}),
            "mongo_access_points": len(mongo_access),
            "mongo_write_operations": len(mongo_writes),
            "worker_mongo_write_files": len(worker_write_files),
        },
        "contracts": contracts,
        "missing_response_models": missing_response_models,
        "raw_request_bodies": raw_request_bodies,
        "mongo_access": mongo_access,
        "mongo_writes": mongo_writes,
        "worker_mongo_write_files": sorted(worker_write_files),
    }

    if output_path is not None:
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(inventory, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )

    return inventory


class _InventoryVisitor(ast.NodeVisitor):
    def __init__(self, path: str) -> None:
        self.path = path
        self.contracts: list[dict[str, Any]] = []
        self.missing_response_models: list[dict[str, Any]] = []
        self.raw_request_bodies: list[dict[str, Any]] = []
        self.mongo_access: list[dict[str, Any]] = []
        self.mongo_writes: list[dict[str, Any]] = []
        self._collection_alias_stack: list[dict[str, str]] = []
        self._class_collection_alias_stack: list[dict[str, str]] = []
        self._module_constants: dict[str, str] = {}

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            if alias.name in MONGO_IMPORT_MODULES:
                self.mongo_access.append(
                    {
                        "path": self.path,
                        "kind": "import",
                        "line": node.lineno,
                        "symbol": alias.name,
                    }
                )
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        module = node.module or ""
        if module in MONGO_IMPORT_MODULES:
            symbols = [alias.name for alias in node.names]
            self.mongo_access.append(
                {
                    "path": self.path,
                    "kind": "import_from",
                    "line": node.lineno,
                    "symbol": module,
                    "names": symbols,
                }
            )
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_function(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._class_collection_alias_stack.append({})
        try:
            self.generic_visit(node)
        finally:
            self._class_collection_alias_stack.pop()

    def visit_Assign(self, node: ast.Assign) -> None:
        aliases = self._combined_collection_aliases()
        collection = _collection_name(node.value, aliases)
        literal_value = _string_literal_or_alias(node.value, aliases)
        if collection:
            for target in node.targets:
                if isinstance(target, ast.Name):
                    self._current_collection_aliases()[target.id] = collection
                elif _self_attribute_name(target) is not None:
                    self._current_class_collection_aliases()[_self_attribute_name(target)] = collection
        if literal_value:
            for target in node.targets:
                if not self._collection_alias_stack and isinstance(target, ast.Name):
                    self._module_constants[target.id] = literal_value
                elif _self_attribute_name(target) is not None:
                    self._current_class_collection_aliases()[_self_attribute_name(target)] = literal_value
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        function_name = _call_name(node.func)
        if function_name in MONGO_HELPERS:
            self.mongo_access.append(
                {
                    "path": self.path,
                    "kind": "helper_call",
                    "line": node.lineno,
                    "symbol": function_name,
                }
            )
        if function_name in MONGO_WRITE_METHODS:
            self.mongo_writes.append(
                {
                    "path": self.path,
                    "line": node.lineno,
                    "operation": function_name,
                    "collection": _collection_name(
                        node.func.value if isinstance(node.func, ast.Attribute) else None,
                        self._combined_collection_aliases(),
                    ),
                }
            )
        self.generic_visit(node)

    def _visit_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        self._collection_alias_stack.append({})
        routes = []
        try:
            for decorator in node.decorator_list:
                route = _http_route(decorator)
                if route is not None:
                    routes.append(route)
                contract = _response_model_dict_contract(decorator)
                if contract is not None:
                    self.contracts.append(
                        {
                            "path": self.path,
                            "line": node.lineno,
                            "function": node.name,
                            **contract,
                        }
                    )
                missing_response_model = _missing_response_model_contract(decorator)
                if missing_response_model is not None:
                    self.missing_response_models.append(
                        {
                            "path": self.path,
                            "line": node.lineno,
                            "function": node.name,
                            **missing_response_model,
                        }
                    )
            if routes:
                for arg, default in _iter_function_parameters(node):
                    if _is_raw_dict_annotation(arg.annotation) and not _is_dependency_default(default):
                        self.raw_request_bodies.append(
                            {
                                "path": self.path,
                                "line": arg.lineno,
                                "function": node.name,
                                "parameter": arg.arg,
                                "routes": routes,
                            }
                        )
            self.generic_visit(node)
        finally:
            self._collection_alias_stack.pop()

    def _current_collection_aliases(self) -> dict[str, str]:
        if not self._collection_alias_stack:
            self._collection_alias_stack.append({})
        return self._collection_alias_stack[-1]

    def _current_class_collection_aliases(self) -> dict[str, str]:
        if not self._class_collection_alias_stack:
            self._class_collection_alias_stack.append({})
        return self._class_collection_alias_stack[-1]

    def _combined_collection_aliases(self) -> dict[str, str]:
        combined = dict(self._module_constants)
        if self._class_collection_alias_stack:
            combined.update(self._class_collection_alias_stack[-1])
        if self._collection_alias_stack:
            combined.update(self._collection_alias_stack[-1])
        return combined


def _http_route(decorator: ast.AST) -> dict[str, Any] | None:
    if not isinstance(decorator, ast.Call):
        return None

    method = _call_name(decorator.func)
    if method not in HTTP_DECORATORS:
        return None

    route = ""
    if decorator.args and isinstance(decorator.args[0], ast.Constant):
        route = str(decorator.args[0].value)

    return {"method": method.upper(), "route": route}


def _response_model_dict_contract(decorator: ast.AST) -> dict[str, Any] | None:
    route = _http_route(decorator)
    if route is None or not isinstance(decorator, ast.Call):
        return None

    has_response_model_dict = any(
        keyword.arg == "response_model"
        and _contains_raw_dict_annotation(keyword.value)
        for keyword in decorator.keywords
    )
    if not has_response_model_dict:
        return None

    return route


def _missing_response_model_contract(decorator: ast.AST) -> dict[str, Any] | None:
    route = _http_route(decorator)
    if route is None or not isinstance(decorator, ast.Call):
        return None

    has_response_model_keyword = any(keyword.arg == "response_model" for keyword in decorator.keywords)
    if has_response_model_keyword:
        return None
    return route


def _is_raw_dict_annotation(annotation: ast.AST | None) -> bool:
    if annotation is None:
        return False
    if isinstance(annotation, ast.Name):
        return annotation.id in {"dict", "Dict"}
    if isinstance(annotation, ast.Attribute):
        return _call_name(annotation) in {"dict", "Dict"}
    if isinstance(annotation, ast.Subscript):
        name = _call_name(annotation.value)
        return name in {"dict", "Dict"}
    return False


def _contains_raw_dict_annotation(annotation: ast.AST | None) -> bool:
    if annotation is None:
        return False
    if _is_raw_dict_annotation(annotation):
        return True
    if isinstance(annotation, ast.Subscript):
        return _contains_raw_dict_annotation(annotation.slice)
    if isinstance(annotation, ast.Tuple):
        return any(_contains_raw_dict_annotation(element) for element in annotation.elts)
    return False


def _iter_function_parameters(node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[tuple[ast.arg, ast.AST | None]]:
    positional_args = [*node.args.posonlyargs, *node.args.args]
    positional_defaults: list[ast.AST | None] = [None] * (len(positional_args) - len(node.args.defaults)) + list(node.args.defaults)
    keyword_defaults = list(node.args.kw_defaults)
    return [
        *zip(positional_args, positional_defaults, strict=True),
        *zip(node.args.kwonlyargs, keyword_defaults, strict=True),
    ]


def _is_dependency_default(default: ast.AST | None) -> bool:
    if not isinstance(default, ast.Call):
        return False
    return _call_name(default.func) in {"Depends", "Security"}


def _collection_name(node: ast.AST | None, aliases: dict[str, str]) -> str | None:
    if node is None:
        return None
    if isinstance(node, ast.Name):
        return aliases.get(node.id)
    if isinstance(node, ast.Attribute):
        self_alias = _self_attribute_name(node)
        if self_alias is not None:
            return aliases.get(self_alias)
        if node.attr in MONGO_WRITE_METHODS:
            return None
        return node.attr
    if isinstance(node, ast.Subscript):
        if isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, str):
            return node.slice.value
        return _string_literal_or_alias(node.slice, aliases)
    return None


def _string_literal_or_alias(node: ast.AST | None, aliases: dict[str, str]) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Name):
        return aliases.get(node.id)
    self_alias = _self_attribute_name(node)
    if self_alias is not None:
        return aliases.get(self_alias)
    return None


def _self_attribute_name(node: ast.AST | None) -> str | None:
    if (
        isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "self"
    ):
        return f"self.{node.attr}"
    return None


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return ""


def _iter_python_files(root: Path) -> list[Path]:
    return [
        path
        for path in root.rglob("*.py")
        if "__pycache__" not in path.parts and ".venv" not in path.parts
    ]


def _rel(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate PostgreSQL migration inventory.")
    parser.add_argument("--root", default=Path(__file__).resolve().parents[1])
    parser.add_argument(
        "--output",
        default=Path(__file__).resolve().parents[2] / "docs" / "migration" / "postgres_inventory.json",
    )
    parser.add_argument(
        "--allow-contract-regressions",
        action="store_true",
        help="Print the inventory report but exit zero when router contract regressions are found.",
    )
    args = parser.parse_args()

    inventory = scan_backend(args.root, args.output)
    print(json.dumps(inventory["summary"], ensure_ascii=False, indent=2, sort_keys=True))
    if not args.allow_contract_regressions and _has_contract_regressions(inventory["summary"]):
        raise SystemExit(1)


def _has_contract_regressions(summary: dict[str, Any]) -> bool:
    return bool(summary.get("response_model_dict_endpoints") or summary.get("raw_dict_request_bodies"))


if __name__ == "__main__":
    main()
