from __future__ import annotations

from trader.factors.registry import FactorRegistry


class AlphaZooService:
    def __init__(self, registry: FactorRegistry | None = None) -> None:
        self.registry = registry or FactorRegistry.discover()

    def list_factors(
        self,
        *,
        family: str | None = None,
        zoo: str | None = None,
        theme: str | None = None,
        universe: str | None = None,
        search: str | None = None,
        limit: int | None = None,
    ) -> dict[str, object]:
        zoo_filter = zoo or family
        items = [self._metadata_dict(factor_id) for factor_id in self.registry.ids()]
        if zoo_filter:
            items = [item for item in items if item["zoo"] == zoo_filter]
        if theme:
            items = [item for item in items if theme in item["theme"]]
        if universe:
            items = [item for item in items if universe in item["universe"]]
        if search:
            needle = search.lower()
            items = [
                item
                for item in items
                if needle in str(item["factor_id"]).lower()
                or needle in str(item["id"]).lower()
                or needle in str(item["name"]).lower()
                or needle in str(item["nickname"]).lower()
                or needle in str(item["description"]).lower()
                or needle in str(item["formula_latex"]).lower()
            ]
        total = len(items)
        capped_items = items[:limit] if limit and limit > 0 else items
        return {
            "items": capped_items,
            "alphas": capped_items,
            "total": total,
            "returned": len(capped_items),
            "truncated": len(capped_items) < total,
            "health": self.registry.health(),
        }

    def get_factor(self, alpha_id: str) -> dict[str, object] | None:
        try:
            item = self._metadata_dict(alpha_id)
            return {
                **item,
                "alpha": {
                    "id": item["id"],
                    "zoo": item["zoo"],
                    "module_path": item["module_path"],
                    "meta": item["meta"],
                },
                "source_code": self.registry.get_source(alpha_id),
            }
        except KeyError:
            return None

    def _metadata_dict(self, factor_id: str) -> dict[str, object]:
        factor = self.registry.get(factor_id)
        metadata = factor.metadata
        alpha = factor.alpha
        meta = dict(alpha.meta)
        columns_required = list(meta.get("columns_required", metadata.required_columns))
        return {
            "factor_id": metadata.factor_id,
            "id": alpha.id,
            "family": metadata.family,
            "zoo": alpha.zoo,
            "number": metadata.number,
            "name": metadata.name,
            "nickname": meta.get("nickname") or "",
            "description": metadata.description,
            "required_columns": columns_required,
            "columns_required": columns_required,
            "theme": list(meta.get("theme", [])),
            "formula_latex": meta.get("formula_latex") or "",
            "extras_required": list(meta.get("extras_required", [])),
            "requires_sector": bool(meta.get("requires_sector", False)),
            "universe": list(meta.get("universe", [])),
            "frequency": list(meta.get("frequency", [])),
            "decay_horizon": meta.get("decay_horizon"),
            "min_warmup_bars": meta.get("min_warmup_bars"),
            "notes": meta.get("notes") or "",
            "module_path": alpha.module_path,
            "meta": meta,
        }
