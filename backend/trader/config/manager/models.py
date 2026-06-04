# ruff: noqa: F403,F405
from .common import *


class CostResult(float):
    """Float-compatible cost value that can still be unpacked as (cost, currency)."""

    def __new__(cls, value: float, currency: str = "CNY"):
        obj = float.__new__(cls, value)
        cast(Any, obj).currency = currency
        return obj

    def __iter__(self):
        yield float(self)
        yield cast(Any, self).currency
