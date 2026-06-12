from app.services.research.agent.flow.graph import build_stock_dag_parity_plan


def test_default_graph_nodes_and_analyst_order():
    plan = build_stock_dag_parity_plan(
        selected_analysts=None,
        final_decision_engine="risk_manager",
    )

    assert [spec.key for spec in plan.analyst_specs] == [
        "market",
        "social",
        "news",
        "fundamentals",
    ]
    assert plan.first_node == "Market Analyst"
    assert plan.final_risk_node == "Risk Judge"
    assert plan.nodes == [
        "Market Analyst",
        "tools_market",
        "Msg Clear Market",
        "Sentiment Analyst",
        "tools_social",
        "Msg Clear Social",
        "News Analyst",
        "tools_news",
        "Msg Clear News",
        "Fundamentals Analyst",
        "tools_fundamentals",
        "Msg Clear Fundamentals",
        "Bull Researcher",
        "Bear Researcher",
        "Research Manager",
        "Trader",
        "Risky Analyst",
        "Safe Analyst",
        "Neutral Analyst",
        "Risk Judge",
        "END",
    ]


def test_normal_and_conditional_edges_match_old_dag():
    plan = build_stock_dag_parity_plan(
        selected_analysts=None,
        final_decision_engine="risk_manager",
    )

    assert ("START", "Market Analyst") in plan.normal_edges
    assert ("tools_market", "Market Analyst") in plan.normal_edges
    assert ("Msg Clear Market", "Sentiment Analyst") in plan.normal_edges
    assert ("Msg Clear Social", "News Analyst") in plan.normal_edges
    assert ("Msg Clear News", "Fundamentals Analyst") in plan.normal_edges
    assert ("Msg Clear Fundamentals", "Bull Researcher") in plan.normal_edges
    assert ("Research Manager", "Trader") in plan.normal_edges
    assert ("Trader", "Risky Analyst") in plan.normal_edges
    assert ("Risk Judge", "END") in plan.normal_edges

    assert plan.conditional_edges["Market Analyst"].targets == [
        "tools_market",
        "Msg Clear Market",
    ]
    assert plan.conditional_edges["Bull Researcher"].target_map == {
        "Bear Researcher": "Bear Researcher",
        "Research Manager": "Research Manager",
    }
    assert plan.conditional_edges["Risky Analyst"].target_map == {
        "Safe Analyst": "Safe Analyst",
        "Risk Judge": "Risk Judge",
    }


def test_portfolio_manager_final_risk_mode():
    plan = build_stock_dag_parity_plan(
        selected_analysts=["market"],
        final_decision_engine="portfolio_manager",
    )

    assert plan.nodes[-2:] == ["Portfolio Manager", "END"]
    assert ("Risky Analyst", "Portfolio Manager") in plan.resolved_conditional_targets
    assert ("Safe Analyst", "Portfolio Manager") in plan.resolved_conditional_targets
    assert ("Neutral Analyst", "Portfolio Manager") in plan.resolved_conditional_targets


def test_include_risk_false_bypasses_risk_execution_path():
    plan = build_stock_dag_parity_plan(
        selected_analysts=["market"],
        final_decision_engine="risk_manager",
        include_risk=False,
    )

    assert ("Trader", "END") in plan.normal_edges
    assert ("Trader", "Risky Analyst") not in plan.normal_edges
    assert "Risky Analyst" in plan.skipped_nodes
    assert "Safe Analyst" in plan.skipped_nodes
    assert "Neutral Analyst" in plan.skipped_nodes
    assert "Risk Judge" in plan.skipped_nodes
    assert "Portfolio Manager" in plan.skipped_nodes
    assert plan.stage_status_overrides["risk_debate"] == "skipped"
    assert plan.stage_status_overrides["final_risk_decision"] == "skipped"
