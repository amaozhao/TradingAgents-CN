from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.query_plan_checker import (
    assert_required_plans_do_not_filter_payload,
    collect_query_plans,
    query_plan_result_without_execution,
    representative_query_plan_specs,
)


async def _run_cli(*, fail_on_payload: bool) -> dict:
    from app.db.session import close_postgres, get_session_factory, init_postgres

    await init_postgres()
    try:
        async with get_session_factory()() as session:
            results = await collect_query_plans(session)
        if fail_on_payload:
            assert_required_plans_do_not_filter_payload(results)
        return {
            "all_required_without_payload_filter": not any(result.uses_payload_filter for result in results),
            "queries": {result.name: result.to_dict() for result in results},
        }
    finally:
        await close_postgres()


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect PostgreSQL EXPLAIN plans for migration representative queries.")
    parser.add_argument(
        "--allow-payload-filter",
        action="store_true",
        help="Do not fail when a representative high-frequency query uses payload JSONB filtering.",
    )
    parser.add_argument(
        "--compile-only",
        action="store_true",
        help="Only compile representative EXPLAIN SQL without connecting to PostgreSQL.",
    )
    args = parser.parse_args()

    if args.compile_only:
        results = [
            query_plan_result_without_execution(spec)
            for spec in representative_query_plan_specs()
        ]
        if not args.allow_payload_filter:
            assert_required_plans_do_not_filter_payload(results)
        summary = {
            "all_required_without_payload_filter": not any(result.uses_payload_filter for result in results),
            "queries": {result.name: result.to_dict() for result in results},
        }
    else:
        summary = asyncio.run(_run_cli(fail_on_payload=not args.allow_payload_filter))
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True, default=str))


if __name__ == "__main__":
    main()
