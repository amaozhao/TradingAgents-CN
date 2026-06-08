from __future__ import annotations

from trader.factors.registry import FactorRegistry


class AlphaZooService:
    def __init__(self, registry: FactorRegistry | None = None) -> None:
        self.registry = registry or FactorRegistry.discover()

    def list_factors(
        self,
        *,
        family: str | None = None,
        search: str | None = None,
    ) -> dict[str, object]:
        items = [self._metadata_dict(factor_id) for factor_id in self.registry.ids()]
        if family:
            items = [item for item in items if item["family"] == family]
        if search:
            needle = search.lower()
            items = [
                item
                for item in items
                if needle in item["factor_id"].lower()
                or needle in item["name"].lower()
                or needle in item["description"].lower()
            ]
        return {"items": items, "total": len(items)}

    def get_factor(self, alpha_id: str) -> dict[str, object] | None:
        try:
            return self._metadata_dict(alpha_id)
        except KeyError:
            return None

    def _metadata_dict(self, factor_id: str) -> dict[str, object]:
        metadata = self.registry.get(factor_id).metadata
        return {
            "factor_id": metadata.factor_id,
            "family": metadata.family,
            "number": metadata.number,
            "name": metadata.name,
            "description": metadata.description,
            "required_columns": list(metadata.required_columns),
        }
