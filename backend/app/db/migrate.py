from __future__ import annotations

import argparse
import asyncio
import importlib
import json
from collections.abc import Callable
from typing import Any

from app.db.document import iter_user_favorite_documents
from app.db.write import (
    build_analysis_batch_upsert,
    build_analysis_report_upsert,
    build_analysis_result_upsert,
    build_analysis_task_upsert,
    build_database_backup_upsert,
    build_internal_message_upsert,
    build_login_attempt_upsert,
    build_market_quote_upsert,
    build_notification_upsert,
    build_operation_log_upsert,
    build_paper_account_upsert,
    build_paper_order_upsert,
    build_paper_position_upsert,
    build_paper_trade_upsert,
    build_scheduler_execution_upsert,
    build_scheduler_history_upsert,
    build_scheduler_metadata_upsert,
    build_social_media_message_upsert,
    build_stock_basic_info_upsert,
    build_stock_daily_quote_upsert,
    build_stock_financial_data_upsert,
    build_stock_news_upsert,
    build_sync_status_upsert,
    build_system_config_document_upsert,
    build_token_usage_upsert,
    build_user_account_upsert,
    build_user_favorite_upsert,
    build_user_session_upsert,
    build_user_tag_upsert,
)

HOT_COLLECTIONS: dict[str, Callable[[dict[str, Any]], Any]] = {
    "stock_basic_info": build_stock_basic_info_upsert,
    "market_quotes": build_market_quote_upsert,
    "stock_daily_quotes": build_stock_daily_quote_upsert,
    "stock_financial_data": build_stock_financial_data_upsert,
    "stock_news": build_stock_news_upsert,
    "analysis_tasks": build_analysis_task_upsert,
    "analysis_reports": build_analysis_report_upsert,
    "analysis_batches": build_analysis_batch_upsert,
    "analysis_results": build_analysis_result_upsert,
    "sync_status": build_sync_status_upsert,
    "quotes_ingestion_status": build_sync_status_upsert,
    "scheduler_executions": build_scheduler_execution_upsert,
    "scheduler_history": build_scheduler_history_upsert,
    "scheduler_metadata": build_scheduler_metadata_upsert,
    "system_configs": lambda document: build_system_config_document_upsert(
        document, collection="system_configs"
    ),
    "llm_providers": lambda document: build_system_config_document_upsert(
        document, collection="llm_providers"
    ),
    "model_catalog": lambda document: build_system_config_document_upsert(
        document, collection="model_catalog"
    ),
    "market_categories": lambda document: build_system_config_document_upsert(
        document, collection="market_categories"
    ),
    "datasource_groupings": lambda document: build_system_config_document_upsert(
        document, collection="datasource_groupings"
    ),
    "user_favorites": lambda document: [
        build_user_favorite_upsert(favorite)
        for favorite in iter_user_favorite_documents(document)
    ],
    "user_tags": build_user_tag_upsert,
    "paper_accounts": build_paper_account_upsert,
    "paper_positions": build_paper_position_upsert,
    "paper_orders": build_paper_order_upsert,
    "paper_trades": build_paper_trade_upsert,
    "users": build_user_account_upsert,
    "users_collection": build_user_account_upsert,
    "user_sessions": build_user_session_upsert,
    "login_attempts": build_login_attempt_upsert,
    "operation_logs": build_operation_log_upsert,
    "database_backups": build_database_backup_upsert,
    "notifications": build_notification_upsert,
    "token_usage": build_token_usage_upsert,
    "internal_messages": build_internal_message_upsert,
    "social_media_messages": build_social_media_message_upsert,
}


async def migrate_hot_collections(
    postgres_db, session_factory, batch_size: int = 500
) -> dict[str, dict[str, int]]:
    summary: dict[str, dict[str, int]] = {}
    for collection_name, statement_builder in HOT_COLLECTIONS.items():
        summary[collection_name] = await migrate_collection(
            postgres_db=postgres_db,
            session_factory=session_factory,
            collection_name=collection_name,
            statement_builder=statement_builder,
            batch_size=batch_size,
        )
    return summary


async def migrate_collection(
    postgres_db,
    session_factory,
    collection_name: str,
    statement_builder: Callable[[dict[str, Any]], Any],
    batch_size: int = 500,
) -> dict[str, int]:
    migrated = 0
    commits = 0
    pending = 0
    cursor = postgres_db[collection_name].find({}).batch_size(batch_size)

    async with session_factory() as session:
        async for document in cursor:
            statements = _statements_from_builder(statement_builder, document)
            for statement in statements:
                await session.execute(statement)
                migrated += 1
                pending += 1

                if pending >= batch_size:
                    await session.commit()
                    commits += 1
                    pending = 0

        if pending:
            await session.commit()
            commits += 1

    return {"migrated": migrated, "commits": commits}


def _statements_from_builder(statement_builder, document: dict[str, Any]) -> list[Any]:
    statements = statement_builder(document)
    if isinstance(statements, list | tuple):
        return list(statements)
    return [statements]


async def _run_cli(batch_size: int) -> dict[str, dict[str, int]]:
    close_postgres_document_store_only = getattr(
        importlib.import_module("app.core.database"),
        "close_postgres_document_store_only",
    )
    get_postgres_db = getattr(
        importlib.import_module("app.core.database"), "get_postgres_db"
    )
    init_postgres_document_store_only = getattr(
        importlib.import_module("app.core.database"),
        "init_postgres_document_store_only",
    )
    close_postgres = getattr(
        importlib.import_module("app.db.session"), "close_postgres"
    )
    get_session_factory = getattr(
        importlib.import_module("app.db.session"), "get_session_factory"
    )
    init_postgres = getattr(importlib.import_module("app.db.session"), "init_postgres")

    await init_postgres_document_store_only()
    await init_postgres()
    try:
        return await migrate_hot_collections(
            get_postgres_db(), get_session_factory(), batch_size=batch_size
        )
    finally:
        await close_postgres()
        await close_postgres_document_store_only()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Migrate PostgreSQL hot collections to PostgreSQL."
    )
    parser.add_argument("--batch-size", type=int, default=500)
    args = parser.parse_args()

    summary = asyncio.run(_run_cli(batch_size=args.batch_size))
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
