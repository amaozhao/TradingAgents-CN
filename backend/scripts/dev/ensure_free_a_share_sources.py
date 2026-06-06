from __future__ import annotations

from app.db.store import create_sync_client
from app.utils.timezone import now_tz


BAOSTOCK_CONFIG = {
    "name": "BaoStock",
    "type": "baostock",
    "api_key": None,
    "api_secret": None,
    "endpoint": "http://baostock.com",
    "timeout": 30,
    "rate_limit": 60,
    "enabled": True,
    "priority": 0,
    "config_params": {},
    "description": "BaoStock免费A股数据接口",
    "market_categories": ["a_shares"],
    "display_name": "BaoStock",
    "provider": "BaoStock",
}


def main() -> None:
    client = create_sync_client()
    try:
        db = client["trading_agents"]
        collection = db.system_configs
        config = collection.find_one({"is_active": True}, sort=[("version", -1)])
        if not config:
            print("no active system config found")
            return

        data_sources = list(config.get("data_source_configs") or [])
        existing_types = {
            str(item.get("type") or "").lower()
            for item in data_sources
            if isinstance(item, dict)
        }
        if "baostock" in existing_types:
            print(
                "baostock already configured",
                {
                    "config_id": str(config.get("_id")),
                    "data_source_count": len(data_sources),
                },
            )
            return

        now = now_tz()
        data_sources.append({**BAOSTOCK_CONFIG, "created_at": now, "updated_at": now})
        result = collection.update_one(
            {"_id": config["_id"]},
            {
                "$set": {
                    "data_source_configs": data_sources,
                    "updated_at": now,
                }
            },
        )
        print(
            "baostock configured",
            {
                "config_id": str(config.get("_id")),
                "matched": result.matched_count,
                "modified": result.modified_count,
                "data_source_count": len(data_sources),
            },
        )
    finally:
        client.close()


if __name__ == "__main__":
    main()
