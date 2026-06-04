# ruff: noqa: F401,F403,F405,F821
class SyncPostgresCollection:
    def __init__(self, async_collection: PostgresCollection):
        self._async = async_collection

    def find_one(self, *args, **kwargs) -> Any:
        return _run_blocking(self._async.find_one(*args, **kwargs))

    def find(self, *args, **kwargs) -> PostgresCursor:
        return self._async.find(*args, **kwargs)

    def count_documents(self, *args, **kwargs) -> int:
        return _run_blocking(self._async.count_documents(*args, **kwargs))

    def estimated_document_count(self, *args, **kwargs) -> int:
        return _run_blocking(self._async.estimated_document_count(*args, **kwargs))

    def insert_one(self, *args, **kwargs) -> InsertOneResult:
        return _run_blocking(self._async.insert_one(*args, **kwargs))

    def insert_many(self, *args, **kwargs) -> InsertManyResult:
        return _run_blocking(self._async.insert_many(*args, **kwargs))

    def update_one(self, *args, **kwargs) -> UpdateResult:
        return _run_blocking(self._async.update_one(*args, **kwargs))

    def update_many(self, *args, **kwargs) -> UpdateResult:
        return _run_blocking(self._async.update_many(*args, **kwargs))

    def replace_one(self, *args, **kwargs) -> UpdateResult:
        return _run_blocking(self._async.replace_one(*args, **kwargs))

    def delete_one(self, *args, **kwargs) -> DeleteResult:
        return _run_blocking(self._async.delete_one(*args, **kwargs))

    def delete_many(self, *args, **kwargs) -> DeleteResult:
        return _run_blocking(self._async.delete_many(*args, **kwargs))

    def bulk_write(self, *args, **kwargs) -> BulkWriteResult:
        return _run_blocking(self._async.bulk_write(*args, **kwargs))

    def aggregate(self, *args, **kwargs) -> PostgresCursor:
        return self._async.aggregate(*args, **kwargs)

    def distinct(self, *args, **kwargs) -> list[Any]:
        return _run_blocking(self._async.distinct(*args, **kwargs))

    def create_index(self, *args, **kwargs) -> str:
        return _run_blocking(self._async.create_index(*args, **kwargs))

    def drop(self) -> Any:
        return _run_blocking(self._async.drop())
