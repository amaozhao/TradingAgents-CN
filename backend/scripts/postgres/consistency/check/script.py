from __future__ import annotations

import argparse
import asyncio
import importlib
import json

from app.db.consistency import compare_hot_collections, consistency_summary_to_dict


async def _run_cli(sample_limit: int) -> dict:
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
        importlib.import_module("app.core.session"), "close_postgres"
    )
    get_session_factory = getattr(
        importlib.import_module("app.core.session"), "get_session_factory"
    )
    init_postgres = getattr(
        importlib.import_module("app.core.session"), "init_postgres"
    )

    await init_postgres_document_store_only()
    await init_postgres()
    try:
        results = await compare_hot_collections(
            get_postgres_db(), get_session_factory(), sample_limit=sample_limit
        )
        return consistency_summary_to_dict(results)
    finally:
        await close_postgres()
        await close_postgres_document_store_only()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare PostgreSQL and PostgreSQL hot collection consistency."
    )
    parser.add_argument("--sample-limit", type=int, default=500)
    parser.add_argument(
        "--allow-inconsistent",
        action="store_true",
        help="Print the consistency report but exit zero even when inconsistencies are found.",
    )
    args = parser.parse_args()

    summary = asyncio.run(_run_cli(sample_limit=args.sample_limit))
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    if not args.allow_inconsistent and summary.get("all_consistent") is not True:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
