# ruff: noqa: F401,F403,F405,F821
@dataclass(frozen=True)
class InsertOneResult:
    inserted_id: Any
    acknowledged: bool = True


@dataclass(frozen=True)
class InsertManyResult:
    inserted_ids: list[Any]
    acknowledged: bool = True


@dataclass(frozen=True)
class UpdateResult:
    matched_count: int = 0
    modified_count: int = 0
    upserted_id: Any = None
    acknowledged: bool = True


@dataclass(frozen=True)
class DeleteResult:
    deleted_count: int = 0
    acknowledged: bool = True


@dataclass(frozen=True)
class BulkWriteResult:
    matched_count: int = 0
    modified_count: int = 0
    upserted_ids: dict[int, Any] = field(default_factory=dict)

    @property
    def upserted_count(self) -> int:
        return len(self.upserted_ids)


class BulkWriteError(Exception):
    """PostgreSQL document-store bulk write error."""

    def __init__(self, details: dict[str, Any] | None = None):
        super().__init__(details or {})
        self.details = details or {}


class UpdateOne:
    def __init__(
        self,
        filter: dict[str, Any],
        update: dict[str, Any] | None = None,
        *,
        upsert: bool = False,
        **kwargs: Any,
    ):
        self._filter = filter
        self._doc = update if update is not None else kwargs.get("doc", {})
        self._upsert = upsert


class ReplaceOne:
    def __init__(
        self,
        filter: dict[str, Any] | None = None,
        replacement: dict[str, Any] | None = None,
        *,
        upsert: bool = False,
        **kwargs: Any,
    ):
        self._filter = filter if filter is not None else kwargs.get("filter", {})
        self._doc = (
            replacement
            if replacement is not None
            else kwargs.get("replacement", kwargs.get("doc", {}))
        )
        self._upsert = upsert


class InsertOne:
    def __init__(self, document: dict[str, Any] | None = None, **kwargs: Any):
        self._doc = (
            document
            if document is not None
            else kwargs.get("document", kwargs.get("doc", {}))
        )


class DeleteOne:
    def __init__(self, filter: dict[str, Any] | None = None, **kwargs: Any):
        self._filter = filter if filter is not None else kwargs.get("filter", {})


class DeleteMany:
    def __init__(self, filter: dict[str, Any] | None = None, **kwargs: Any):
        self._filter = filter if filter is not None else kwargs.get("filter", {})
