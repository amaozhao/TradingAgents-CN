# ruff: noqa: F401,F403,F405,F821
from __future__ import annotations

import copy
from collections.abc import Awaitable, Callable, Iterator
from typing import Any, Self, cast

from .helpers import _get_value, _normalize_sort, _run_blocking, _sort_key


class PostgresCursor:
    def __init__(
        self,
        documents: list[dict[str, Any]] | None = None,
        loader: Callable[[], Awaitable[list[dict[str, Any]]]] | None = None,
    ):
        self._documents = documents
        self._loader = loader
        self._skip = 0
        self._limit: int | None = None
        self._index = 0
        self._sort_items: list[tuple[str, int]] = []

    def sort(self, key_or_list: Any, direction: int | None = None) -> Self:
        self._sort_items.extend(_normalize_sort(key_or_list, direction))
        return self

    def skip(self, count: int) -> Self:
        self._skip = max(count, 0)
        return self

    def limit(self, count: int | None) -> Self:
        self._limit = count if count and count > 0 else None
        return self

    def batch_size(self, _size: int) -> Self:
        return self

    def close(self) -> None:
        return None

    async def to_list(self, length: int | None = None) -> list[dict[str, Any]]:
        items = await self._window()
        if length is not None:
            return items[:length]
        return items

    def __iter__(self) -> Iterator[dict[str, Any]]:
        return iter(cast(list[dict[str, Any]], _run_blocking(self._window())))

    def __aiter__(self) -> Self:
        self._index = 0
        return self

    async def __anext__(self) -> dict[str, Any]:
        items = await self._window()
        if self._index >= len(items):
            raise StopAsyncIteration
        item = items[self._index]
        self._index += 1
        return item

    async def _ensure_loaded(self) -> list[dict[str, Any]]:
        if self._documents is None:
            self._documents = await self._loader() if self._loader is not None else []
            for key, sort_direction in reversed(self._sort_items):
                self._documents.sort(
                    key=lambda document: _sort_key(_get_value(document, key)),
                    reverse=sort_direction < 0,
                )
        return self._documents

    async def _window(self) -> list[dict[str, Any]]:
        documents = await self._ensure_loaded()
        items = documents[self._skip :]
        if self._limit is not None:
            items = items[: self._limit]
        return [copy.deepcopy(item) for item in items]
