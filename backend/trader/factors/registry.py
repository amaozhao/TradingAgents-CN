"""Alpha registry backed by the real bundled factor zoo."""

from __future__ import annotations

import ast
import importlib
import importlib.util
import logging
import re
import sys
import threading
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any, Literal

import numpy as np
import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from trader.factors.base import Alpha, FactorMetadata, Panel

logger = logging.getLogger(__name__)

_ID_RE = re.compile(r"^[a-z][a-z0-9_]{0,31}$")
_MAX_PY_BYTES = 200_000

Theme = Literal[
    "momentum",
    "reversal",
    "volume",
    "volatility",
    "quality",
    "value",
    "liquidity",
    "microstructure",
    "sentiment",
    "growth",
    "leverage",
]
PanelColumn = Literal["open", "high", "low", "close", "volume", "vwap", "amount"]
Universe = Literal["equity_us", "equity_cn", "equity_hk", "crypto", "futures"]


class AlphaMeta(BaseModel):
    """Strict metadata schema loaded from each factor module's __alpha_meta__."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(pattern=r"^[a-z][a-z0-9]+_[a-z0-9_]+$")
    nickname: str | None = None
    theme: list[Theme]
    formula_latex: str
    columns_required: list[PanelColumn]
    extras_required: list[str] = Field(default_factory=list)
    requires_sector: bool = False
    universe: list[Universe]
    frequency: list[str]
    decay_horizon: int = Field(ge=0, le=60)
    min_warmup_bars: int = Field(ge=0)
    notes: str = ""


class SkipAlpha(Exception):
    """Raised when an alpha's input panel is missing required data."""


class RegistryError(Exception):
    """Raised on registry load or compute errors."""


@dataclass(frozen=True, slots=True)
class _LoadError:
    alpha_id: str
    reason: str


def _validate_id_token(token: str, kind: str) -> None:
    if not _ID_RE.fullmatch(token):
        raise RegistryError(f"invalid {kind} {token!r}: must match {_ID_RE.pattern}")


def load_alpha_meta_from_py(path: Path) -> AlphaMeta:
    """AST-extract __alpha_meta__ from a factor module without importing it."""
    size = path.stat().st_size
    if size > _MAX_PY_BYTES:
        raise RegistryError(f"{path.name}: {size}B exceeds {_MAX_PY_BYTES}B cap")

    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))

    meta_node: ast.expr | None = None
    for stmt in tree.body:
        if not isinstance(stmt, ast.Assign):
            continue
        targets = [target for target in stmt.targets if isinstance(target, ast.Name)]
        if any(target.id == "__alpha_meta__" for target in targets):
            meta_node = stmt.value
            break

    if meta_node is None:
        raise RegistryError(f"{path.name}: __alpha_meta__ assignment not found")

    try:
        raw = ast.literal_eval(meta_node)
    except (ValueError, SyntaxError) as exc:
        raise RegistryError(f"{path.name}: __alpha_meta__ not a literal: {exc}") from exc

    if not isinstance(raw, dict):
        raise RegistryError(f"{path.name}: __alpha_meta__ must be dict, got {type(raw).__name__}")

    try:
        return AlphaMeta(**raw)
    except ValidationError as exc:
        raise RegistryError(f"{path.name}: AlphaMeta validation failed: {exc}") from exc


def _zoo_dir_default() -> Path:
    return Path(__file__).parent / "zoo"


class Registry:
    """Scans real factor modules and exposes Vibe-compatible metadata APIs."""

    def __init__(self, zoo_root: Path | None = None) -> None:
        default_root = _zoo_dir_default()
        self._zoo_root = (zoo_root or default_root).resolve()
        self._use_filesystem_loader = self._zoo_root != default_root.resolve()
        self._py_paths: dict[str, Path] = {}
        self._alphas: dict[str, Alpha] = {}
        self._load_errors: list[_LoadError] = []
        self._scan()

    def _scan(self) -> None:
        if not self._zoo_root.is_dir():
            return
        for zoo_dir in sorted(self._zoo_root.iterdir()):
            if not zoo_dir.is_dir():
                continue
            zoo_id = zoo_dir.name
            if zoo_id.startswith("_") or zoo_id == "__pycache__":
                continue
            try:
                _validate_id_token(zoo_id, "zoo_id")
            except RegistryError as exc:
                self._load_errors.append(_LoadError(zoo_id, str(exc)))
                continue
            for py_file in sorted(zoo_dir.rglob("*.py")):
                relative_parts = py_file.relative_to(zoo_dir).parts
                if any(part.startswith("_") or part == "__pycache__" for part in relative_parts):
                    continue
                self._try_register(zoo_id, py_file)

    def _try_register(self, zoo_id: str, py_file: Path) -> None:
        zoo_dir = self._zoo_root / zoo_id
        module_parts = py_file.relative_to(zoo_dir).with_suffix("").parts
        short_id = "_".join(module_parts)
        try:
            _validate_id_token(short_id, "alpha_id_short")
            meta = load_alpha_meta_from_py(py_file)
        except RegistryError as exc:
            self._load_errors.append(_LoadError(f"{zoo_id}.{short_id}", str(exc)))
            return

        module_path = ".".join(("trader", "factors", "zoo", zoo_id, *module_parts))
        alpha = Alpha(id=meta.id, zoo=zoo_id, module_path=module_path, meta=meta.model_dump())
        if alpha.id in self._alphas:
            self._load_errors.append(_LoadError(alpha.id, "duplicate alpha id"))
            return
        self._alphas[alpha.id] = alpha
        self._py_paths[alpha.id] = py_file

    def list(
        self,
        zoo: str | None = None,
        theme: str | None = None,
        universe: str | None = None,
    ) -> list[str]:
        out: list[str] = []
        for alpha in self._alphas.values():
            if zoo is not None and alpha.zoo != zoo:
                continue
            if theme is not None and theme not in alpha.meta.get("theme", []):
                continue
            if universe is not None and universe not in alpha.meta.get("universe", []):
                continue
            out.append(alpha.id)
        return sorted(out)

    def get(self, alpha_id: str) -> Alpha:
        if alpha_id not in self._alphas:
            raise KeyError(f"alpha_id {alpha_id!r} not in registry")
        return self._alphas[alpha_id]

    def get_source(self, alpha_id: str) -> str:
        if alpha_id not in self._alphas:
            raise KeyError(f"alpha_id {alpha_id!r} not in registry")
        py_path = self._py_paths[alpha_id]
        size = py_path.stat().st_size
        if size > _MAX_PY_BYTES:
            raise RegistryError(f"{alpha_id}: source {size}B exceeds {_MAX_PY_BYTES}B cap")
        return py_path.read_text(encoding="utf-8")

    def health(self) -> dict[str, Any]:
        return {
            "loaded": len(self._alphas),
            "failed": len(self._load_errors),
            "errors": [{"alpha_id": error.alpha_id, "reason": error.reason} for error in self._load_errors],
        }

    def compute(self, alpha_id: str, panel: dict[str, pd.DataFrame]) -> pd.DataFrame:
        return self._compute(alpha_id, panel, strict_nan_ratio=True)

    def compute_lenient(self, alpha_id: str, panel: Panel) -> pd.DataFrame:
        frames = {key: value for key, value in panel.items() if isinstance(value, pd.DataFrame)}
        return self._compute(alpha_id, frames, strict_nan_ratio=False)

    def _compute(
        self,
        alpha_id: str,
        panel: dict[str, pd.DataFrame],
        *,
        strict_nan_ratio: bool,
    ) -> pd.DataFrame:
        alpha = self.get(alpha_id)
        meta = alpha.meta

        missing = [column for column in meta.get("columns_required", []) if column not in panel]
        if missing:
            raise SkipAlpha(f"{alpha_id}: panel missing required columns {missing}")
        missing_extra = [column for column in meta.get("extras_required", []) if column not in panel]
        if missing_extra:
            raise SkipAlpha(f"{alpha_id}: panel missing extras {missing_extra}")
        if meta.get("requires_sector") and "sector" not in panel:
            raise SkipAlpha(f"{alpha_id}: panel missing sector tag")

        try:
            module = self._load_module(alpha)
            compute_fn = getattr(module, "compute")
            result = compute_fn(panel)
        except Exception as exc:  # noqa: BLE001
            raise RegistryError(f"{alpha_id}: compute failed: {exc}") from exc

        return self._validate_output(alpha_id, result, panel, strict_nan_ratio=strict_nan_ratio)

    def _load_module(self, alpha: Alpha) -> ModuleType:
        if not self._use_filesystem_loader:
            return importlib.import_module(alpha.module_path)
        py_file = self._py_paths[alpha.id]
        cached = sys.modules.get(alpha.module_path)
        if cached is not None and getattr(cached, "__file__", None) == str(py_file):
            return cached
        spec = importlib.util.spec_from_file_location(alpha.module_path, py_file)
        if spec is None or spec.loader is None:
            raise RegistryError(f"{alpha.id}: could not build import spec for {py_file}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[alpha.module_path] = module
        try:
            spec.loader.exec_module(module)
        except Exception:
            sys.modules.pop(alpha.module_path, None)
            raise
        return module

    @staticmethod
    def _validate_output(
        alpha_id: str,
        result: Any,
        panel: dict[str, pd.DataFrame],
        *,
        strict_nan_ratio: bool,
    ) -> pd.DataFrame:
        if not isinstance(result, pd.DataFrame):
            raise RegistryError(f"{alpha_id}: compute() returned {type(result).__name__}, expected DataFrame")
        ref = panel.get("close")
        if ref is not None and result.shape != ref.shape:
            raise RegistryError(f"{alpha_id}: output shape {result.shape} != close shape {ref.shape}")
        arr = result.to_numpy(dtype=np.float64, na_value=np.nan)
        if np.isinf(arr).any():
            raise RegistryError(f"{alpha_id}: output contains +/- inf")
        if strict_nan_ratio:
            nan_ratio = float(np.isnan(arr).mean()) if arr.size > 0 else 1.0
            if nan_ratio > 0.95:
                raise RegistryError(f"{alpha_id}: output >95% NaN (nan_ratio={nan_ratio:.3f})")
        return result

    def export_manifest(self) -> dict[str, Any]:
        from datetime import datetime, timezone

        zoos: dict[str, list[dict[str, Any]]] = {}
        for alpha in self._alphas.values():
            zoos.setdefault(alpha.zoo, []).append(
                {"id": alpha.id, "module_path": alpha.module_path, "meta": alpha.meta}
            )
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "zoos": [
                {"zoo_id": zoo_id, "alphas": sorted(items, key=lambda item: item["id"])}
                for zoo_id, items in sorted(zoos.items())
            ],
            "health": self.health(),
        }


@dataclass(frozen=True)
class RegisteredFactor:
    """Compatibility wrapper for the older FactorRegistry contract."""

    alpha: Alpha
    registry: Registry

    @property
    def metadata(self) -> FactorMetadata:
        meta = self.alpha.meta
        return FactorMetadata(
            factor_id=self.alpha.id,
            family=self.alpha.zoo,
            number=_numeric_suffix(self.alpha.id),
            name=str(meta.get("nickname") or self.alpha.id),
            description=str(meta.get("formula_latex") or meta.get("notes") or ""),
            required_columns=tuple(meta.get("columns_required", [])),
        )

    def calculate(self, panel: Panel) -> pd.DataFrame:
        return self.registry.compute_lenient(self.alpha.id, panel)


class FactorRegistry:
    """Backward-compatible registry facade used by CN backend jobs/tests."""

    def __init__(self, registry: Registry | None = None) -> None:
        self._registry = registry or get_default_registry()

    @classmethod
    def discover(cls) -> "FactorRegistry":
        return cls(get_default_registry())

    def ids(self) -> list[str]:
        return self._registry.list()

    def get(self, factor_id: str) -> RegisteredFactor:
        return RegisteredFactor(self._registry.get(factor_id), self._registry)

    def all(self) -> list[RegisteredFactor]:
        return [self.get(factor_id) for factor_id in self.ids()]

    def get_source(self, factor_id: str) -> str:
        return self._registry.get_source(factor_id)

    def health(self) -> dict[str, Any]:
        return self._registry.health()

    def raw(self) -> Registry:
        return self._registry


def _numeric_suffix(alpha_id: str) -> int:
    suffix = alpha_id.rsplit("_", 1)[-1]
    return int(suffix) if suffix.isdigit() else 0


_registry_cache: Registry | None = None
_registry_cache_lock = threading.Lock()


def get_default_registry() -> Registry:
    global _registry_cache
    with _registry_cache_lock:
        if _registry_cache is None:
            _registry_cache = Registry()
        return _registry_cache


def reset_default_registry() -> None:
    global _registry_cache
    with _registry_cache_lock:
        _registry_cache = None
