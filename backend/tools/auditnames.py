from __future__ import annotations


APPROVED_ATOMIC_WORDS = {
    "akshare",
    "database",
    "openapi",
    "postgres",
    "runtime",
    "stocktwits",
    "tushare",
}

GLUED_COMPOUNDS = {
    "dataframe": ("data", "frame"),
    "realtime": ("real", "time"),
}


def _validate_single_word_stem(stem: str) -> list[str]:
    normalized = stem.strip().lower()
    if not normalized or normalized in APPROVED_ATOMIC_WORDS:
        return []
    compound = GLUED_COMPOUNDS.get(normalized)
    if compound is None:
        return []
    return [f"filename stem is glued compound words: {compound[0]} + {compound[1]}"]
