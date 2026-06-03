import unittest
from unittest.mock import patch

from app.scripts.normalizeproviderkeys import (
    _should_run,
    normalize_llm_providers,
    normalize_model_catalog,
    normalize_system_configs,
)


class NormalizeProviderKeysScriptTests(unittest.TestCase):
    def test_should_run_honors_include(self):
        self.assertTrue(_should_run("providers", ["providers"], []))
        self.assertFalse(_should_run("model_catalog", ["providers"], []))

    def test_should_run_honors_exclude(self):
        self.assertFalse(_should_run("providers", None, ["providers"]))
        self.assertTrue(_should_run("system_configs", None, ["providers"]))

    def test_normalize_llm_providers_dual_writes_replacement_and_tombstone(self):
        db = _FakeDb(
            llm_providers=[
                {"_id": "1", "name": "qwen", "display_name": "Qwen", "aliases": []},
                {"_id": "2", "name": "dashscope", "display_name": "DashScope", "aliases": []},
            ]
        )
        calls = []

        with patch(
            "app.scripts.normalizeproviderkeys._dual_write_document",
            lambda collection, document: calls.append((collection, document.copy())),
        ), patch(
            "app.scripts.normalizeproviderkeys._dual_write_documents",
            lambda collection, documents: calls.append((collection, [doc.copy() for doc in documents])),
        ):
            summary = normalize_llm_providers(db)

        self.assertEqual(summary["providers_merged"], 1)
        self.assertEqual(calls[0][0], "llm_providers")
        self.assertEqual(calls[0][1]["name"], "qwen")
        self.assertEqual(calls[1][0], "llm_providers")
        self.assertTrue(calls[1][1][0]["deleted"])
        self.assertEqual(db.llm_providers.deleted_queries[0], {"_id": {"$in": ["2"]}})

    def test_normalize_system_configs_dual_writes_updated_document(self):
        db = _FakeDb(
            system_configs=[
                {
                    "_id": "cfg-1",
                    "name": "active",
                    "llm_configs": [{"provider": "dashscope", "model": "qwen-plus"}],
                }
            ]
        )
        calls = []

        with patch(
            "app.scripts.normalizeproviderkeys._dual_write_document",
            lambda collection, document: calls.append((collection, document.copy())),
        ):
            summary = normalize_system_configs(db)

        self.assertEqual(summary["system_configs_changed"], 1)
        self.assertEqual(db.system_configs.updates[0][1]["$set"]["llm_configs"][0]["provider"], "qwen")
        self.assertEqual(calls[0][0], "system_configs")
        self.assertEqual(calls[0][1]["llm_configs"][0]["provider"], "qwen")

    def test_normalize_model_catalog_dual_writes_replacement_and_tombstone(self):
        db = _FakeDb(
            model_catalog=[
                {"_id": "1", "provider": "qwen", "models": [{"name": "qwen-plus"}]},
                {"_id": "2", "provider": "dashscope", "models": [{"name": "qwen-max"}]},
            ]
        )
        calls = []

        with patch(
            "app.scripts.normalizeproviderkeys._dual_write_document",
            lambda collection, document: calls.append((collection, document.copy())),
        ), patch(
            "app.scripts.normalizeproviderkeys._dual_write_documents",
            lambda collection, documents: calls.append((collection, [doc.copy() for doc in documents])),
        ):
            summary = normalize_model_catalog(db)

        self.assertEqual(summary["model_catalog_merged"], 1)
        self.assertEqual(calls[0][0], "model_catalog")
        self.assertEqual(calls[0][1]["provider"], "qwen")
        self.assertEqual(calls[1][0], "model_catalog")
        self.assertTrue(calls[1][1][0]["deleted"])


class _FakeDb:
    def __init__(self, **collections):
        for name, documents in collections.items():
            setattr(self, name, _FakeCollection(documents))


class _FakeCollection:
    def __init__(self, documents):
        self.documents = [doc.copy() for doc in documents]
        self.replacements = []
        self.updates = []
        self.deleted_queries = []

    def find(self):
        return [doc.copy() for doc in self.documents]

    def replace_one(self, query, document):
        self.replacements.append((query, document.copy()))

    def update_one(self, query, update):
        self.updates.append((query, update))

    def delete_many(self, query):
        self.deleted_queries.append(query)

    def create_index(self, *_args, **_kwargs):
        return None


if __name__ == "__main__":
    unittest.main()
