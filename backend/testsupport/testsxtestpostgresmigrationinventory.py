import json
from pathlib import Path

from scripts.postgres_migration_inventory import scan_backend


def test_scan_backend_finds_contracts_mongo_access_and_worker_writes(tmp_path):
    app_dir = tmp_path / "app"
    router_file = app_dir / "routers" / "items.py"
    service_file = app_dir / "services" / "items_service.py"
    worker_file = app_dir / "worker" / "items_worker.py"

    router_file.parent.mkdir(parents=True)
    service_file.parent.mkdir(parents=True)
    worker_file.parent.mkdir(parents=True)

    router_file.write_text(
        """
from fastapi import APIRouter
from typing import Any, Dict, List

router = APIRouter()

@router.get("/items", response_model=dict)
async def get_items(payload: dict):
    return {"items": []}

@router.get("/items/no-model")
async def get_items_without_response_model():
    return {"items": []}

@router.post("/items", response_model=Dict[str, Any])
async def create_item(custom_body: dict[str, Any]):
    return {"ok": True}

@router.get("/item-options", response_model=List[Dict[str, Any]])
async def get_item_options():
    return []
""",
        encoding="utf-8",
    )
    service_file.write_text(
        """
from app.core.coredatabase import get_mongo_db

async def load_item():
    db = get_mongo_db()
    return await db.items.find_one({"legacy_id": "1"})
""",
        encoding="utf-8",
    )
    worker_file.write_text(
        """
from app.core.coredatabase import get_mongo_db

async def persist_item():
    db = get_mongo_db()
    collection = db.items
    await collection.update_one({"legacy_id": "1"}, {"$set": {"name": "a"}}, upsert=True)
""",
        encoding="utf-8",
    )

    inventory = scan_backend(tmp_path)

    assert inventory["summary"]["response_model_dict_endpoints"] == 3
    assert inventory["summary"]["missing_response_model_endpoints"] == 1
    assert inventory["summary"]["raw_dict_request_bodies"] == 2
    assert inventory["summary"]["mongo_access_files"] == 2
    assert inventory["summary"]["mongo_write_operations"] == 1
    assert inventory["summary"]["worker_mongo_write_files"] == 1
    assert inventory["contracts"][0]["path"] == "app/routers/items.py"
    assert inventory["missing_response_models"][0]["path"] == "app/routers/items.py"
    assert inventory["missing_response_models"][0]["route"] == "/items/no-model"
    assert inventory["raw_request_bodies"][0]["parameter"] == "payload"
    assert inventory["mongo_access"][0]["path"] == "app/services/items_service.py"
    assert inventory["mongo_writes"][0]["operation"] == "update_one"
    assert inventory["mongo_writes"][0]["collection"] == "items"


def test_scan_backend_writes_json_report(tmp_path):
    report_path = tmp_path / "inventory.json"

    inventory = scan_backend(tmp_path, output_path=report_path)

    assert report_path.exists()
    assert json.loads(report_path.read_text(encoding="utf-8")) == inventory


def test_scan_backend_resolves_class_collection_aliases_and_module_constants(tmp_path):
    app_dir = tmp_path / "app"
    service_file = app_dir / "services" / "historical_service.py"
    service_file.parent.mkdir(parents=True)

    service_file.write_text(
        """
from app.core.coredatabase import get_mongo_db

DATA_COLLECTION = "stock_basic_info"

class HistoricalService:
    def __init__(self):
        self.collection = None
        self.collection_name = "operation_logs"

    async def initialize(self):
        db = get_mongo_db()
        self.collection = db.stock_daily_quotes

    async def save_quotes(self, operations):
        await self.collection.bulk_write(operations)

    async def write_logs(self, document):
        db = get_mongo_db()
        await db[self.collection_name].insert_one(document)

async def save_basic(operations):
    db = get_mongo_db()
    collection = db[DATA_COLLECTION]
    await collection.bulk_write(operations)
""",
        encoding="utf-8",
    )

    inventory = scan_backend(tmp_path)
    writes = {(item["operation"], item["collection"]) for item in inventory["mongo_writes"]}

    assert ("bulk_write", "stock_daily_quotes") in writes
    assert ("insert_one", "operation_logs") in writes
    assert ("bulk_write", "stock_basic_info") in writes
