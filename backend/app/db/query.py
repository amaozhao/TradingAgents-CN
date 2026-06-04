from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from sqlalchemy import Select, text
from sqlalchemy.dialects import postgresql

from app.db.financial import build_financial_data_query
from app.db.operation import build_operation_log_select
from app.db.paper import build_paper_orders_select, build_paper_positions_select
from app.db.preference import build_user_favorites_select, build_user_tags_select
from app.db.screening import build_screening_select
from app.db.stock import build_list_stock_daily_quotes, build_stock_list
from app.models.operations import OperationLogQuery


@dataclass(frozen=True)
class QueryPlanSpec:
    name: str
    statement: Select
    required_columns: tuple[str, ...]
    allow_payload_filter: bool = False


@dataclass(frozen=True)
class QueryPlanResult:
    name: str
    explain_sql: str
    uses_payload_filter: bool
    required_columns: tuple[str, ...]
    plan: Any | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def representative_query_plan_specs() -> list[QueryPlanSpec]:
    return [
        QueryPlanSpec(
            name="stock_screening",
            statement=build_screening_select(
                conditions=[
                    {"field": "industry", "operator": "==", "value": "银行"},
                    {"field": "pe", "operator": "between", "value": [0, 20]},
                    {"field": "pct_chg", "operator": ">=", "value": 1},
                ],
                limit=50,
                offset=0,
                order_by=[{"field": "total_mv", "direction": "desc"}],
                source="tushare",
            ),
            required_columns=(
                "stock_basic_info.industry",
                "stock_basic_info.pe",
                "market_quotes.pct_chg",
            ),
        ),
        QueryPlanSpec(
            name="stock_list_page",
            statement=build_stock_list(
                source="tushare",
                market="主板",
                industry="银行",
                page=1,
                page_size=50,
            ),
            required_columns=(
                "stock_basic_info.source",
                "stock_basic_info.market",
                "stock_basic_info.industry",
            ),
        ),
        QueryPlanSpec(
            name="daily_quotes_range",
            statement=build_list_stock_daily_quotes(
                market="CN",
                code="000001",
                start_date="2026-01-01",
                end_date="2026-06-03",
                data_source="tushare",
                period="daily",
                limit=120,
            ),
            required_columns=(
                "stock_daily_quotes.trade_date",
                "stock_daily_quotes.market",
                "stock_daily_quotes.data_source",
            ),
        ),
        QueryPlanSpec(
            name="financial_data",
            statement=build_financial_data_query(
                symbol="000001",
                report_period="2025Q4",
                data_source="tushare",
                limit=20,
            ),
            required_columns=(
                "stock_financial_data.code",
                "stock_financial_data.report_period",
                "stock_financial_data.data_source",
            ),
        ),
        QueryPlanSpec(
            name="operation_logs_page",
            statement=build_operation_log_select(
                OperationLogQuery(
                    keyword=None,
                    start_date="2026-06-01T00:00:00",
                    end_date="2026-06-03T23:59:59",
                    action_type="user_login",
                    success=True,
                    user_id="user-1",
                    page=1,
                    page_size=50,
                ),
                offset=0,
                limit=50,
            ),
            required_columns=(
                "operation_logs.timestamp",
                "operation_logs.action_type",
                "operation_logs.success",
                "operation_logs.user_id",
            ),
        ),
        QueryPlanSpec(
            name="user_favorites",
            statement=build_user_favorites_select("user-1"),
            required_columns=("user_favorites.user_id", "user_favorites.deleted"),
        ),
        QueryPlanSpec(
            name="user_tags",
            statement=build_user_tags_select("user-1"),
            required_columns=("user_tags.user_id", "user_tags.deleted"),
        ),
        QueryPlanSpec(
            name="paper_positions",
            statement=build_paper_positions_select("user-1"),
            required_columns=("paper_positions.user_id", "paper_positions.deleted"),
        ),
        QueryPlanSpec(
            name="paper_orders",
            statement=build_paper_orders_select("user-1", limit=50),
            required_columns=(
                "paper_orders.user_id",
                "paper_orders.deleted",
                "paper_orders.created_at",
            ),
        ),
    ]


def explain_sql_for(statement: Select) -> str:
    compiled = statement.compile(
        dialect=postgresql.dialect(),
        compile_kwargs={"literal_binds": True},
    )
    return f"EXPLAIN (FORMAT JSON, COSTS TRUE, BUFFERS TRUE) {compiled}"


def query_plan_result_without_execution(spec: QueryPlanSpec) -> QueryPlanResult:
    explain_sql = explain_sql_for(spec.statement)
    return QueryPlanResult(
        name=spec.name,
        explain_sql=explain_sql,
        uses_payload_filter=_where_clause_uses_payload(explain_sql),
        required_columns=spec.required_columns,
    )


async def collect_query_plans(session) -> list[QueryPlanResult]:
    results: list[QueryPlanResult] = []
    for spec in representative_query_plan_specs():
        base_result = query_plan_result_without_execution(spec)
        execution = await session.execute(text(base_result.explain_sql))
        row = execution.first()
        plan = row[0] if row else None
        results.append(
            QueryPlanResult(
                name=base_result.name,
                explain_sql=base_result.explain_sql,
                uses_payload_filter=base_result.uses_payload_filter,
                required_columns=base_result.required_columns,
                plan=plan,
            )
        )
    return results


def assert_required_plans_do_not_filter_payload(results: list[QueryPlanResult]) -> None:
    offenders = [result.name for result in results if result.uses_payload_filter]
    if offenders:
        raise AssertionError(
            f"Representative high-frequency queries use JSONB payload filters: {offenders}"
        )


def _where_clause_uses_payload(sql: str) -> bool:
    marker = " \nWHERE "
    if marker not in sql:
        marker = "\nWHERE "
    if marker not in sql:
        return False
    where_sql = sql.split(marker, 1)[1]
    for end_marker in ("\n ORDER BY ", "\n GROUP BY ", "\n LIMIT ", "\n OFFSET "):
        if end_marker in where_sql:
            where_sql = where_sql.split(end_marker, 1)[0]
    return "payload" in where_sql
