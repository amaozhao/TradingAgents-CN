from app.db.queryplanchecker import (
    assert_required_plans_do_not_filter_payload,
    query_plan_result_without_execution,
    representative_query_plan_specs,
)


def test_representative_query_plan_specs_cover_cutover_performance_queries():
    specs = representative_query_plan_specs()
    names = {spec.name for spec in specs}

    assert {
        "stock_screening",
        "stock_list_page",
        "daily_quotes_range",
        "financial_data",
        "operation_logs_page",
        "user_favorites",
        "user_tags",
        "paper_positions",
        "paper_orders",
    }.issubset(names)


def test_representative_query_plan_sql_uses_required_split_columns():
    results = [
        query_plan_result_without_execution(spec)
        for spec in representative_query_plan_specs()
    ]

    for result in results:
        assert result.explain_sql.startswith("EXPLAIN (FORMAT JSON")
        for column in result.required_columns:
            assert column in result.explain_sql

    assert_required_plans_do_not_filter_payload(results)
