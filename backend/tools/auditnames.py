from __future__ import annotations


ATOMIC_CODE_WORDS = {
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
    value = stem.strip().lower()
    if not value or value in ATOMIC_CODE_WORDS:
        return []
    parts = GLUED_COMPOUNDS.get(value)
    if parts is None:
        return []
    return [f"filename stem is glued compound words: {parts[0]} + {parts[1]}"]
