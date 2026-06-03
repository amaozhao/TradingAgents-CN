from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.consistencychecker import compare_hot_collections, consistency_summary_to_dict


async def _run_cli(sample_limit: int) -> dict:
    from app.core.coredatabase import close_mongodb_only, get_mongo_db, init_mongodb_only
    from app.db.session import close_postgres, get_session_factory, init_postgres

    await init_mongodb_only()
    await init_postgres()
    try:
        results = await compare_hot_collections(get_mongo_db(), get_session_factory(), sample_limit=sample_limit)
        return consistency_summary_to_dict(results)
    finally:
        await close_postgres()
        await close_mongodb_only()


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare MongoDB and PostgreSQL hot collection consistency.")
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
