# ruff: noqa: F401,F403,F405,F821
class TestDeferredReflection:
    # update_with_outcome

    def test_update_replaces_pending_tag(self, tmp_path):
        log = make_log(tmp_path)
        log.store_decision("NVDA", "2026-01-10", DECISION_BUY)
        log.update_with_outcome(
            "NVDA", "2026-01-10", 0.042, 0.021, 5, "Momentum confirmed."
        )
        text = (tmp_path / "trading_memory.md").read_text(encoding="utf-8")
        assert "[2026-01-10 | NVDA | Buy | pending]" not in text
        assert "+4.2%" in text
        assert "+2.1%" in text
        assert "5d" in text

    def test_update_appends_reflection(self, tmp_path):
        log = make_log(tmp_path)
        log.store_decision("NVDA", "2026-01-10", DECISION_BUY)
        log.update_with_outcome(
            "NVDA", "2026-01-10", 0.042, 0.021, 5, "Momentum confirmed."
        )
        entries = log.load_entries()
        assert len(entries) == 1
        e = entries[0]
        assert e["pending"] is False
        assert e["reflection"] == "Momentum confirmed."
        assert e["decision"] == DECISION_BUY.strip()

    def test_update_preserves_other_entries(self, tmp_path):
        """Only the matching entry is modified; all other entries remain unchanged."""
        log = make_log(tmp_path)
        log.store_decision("NVDA", "2026-01-10", DECISION_BUY)
        log.store_decision("AAPL", "2026-01-11", "Rating: Hold\nHold AAPL.")
        log.store_decision("MSFT", "2026-01-12", DECISION_SELL)
        log.update_with_outcome("AAPL", "2026-01-11", 0.01, -0.01, 5, "Neutral result.")
        entries = log.load_entries()
        assert len(entries) == 3
        nvda, aapl, msft = entries
        assert nvda["ticker"] == "NVDA" and nvda["pending"] is True
        assert aapl["ticker"] == "AAPL" and aapl["pending"] is False
        assert aapl["reflection"] == "Neutral result."
        assert msft["ticker"] == "MSFT" and msft["pending"] is True

    def test_update_atomic_write(self, tmp_path):
        """A pre-existing .tmp file is overwritten; the log is correctly updated."""
        log = make_log(tmp_path)
        log.store_decision("NVDA", "2026-01-10", DECISION_BUY)
        stale_tmp = tmp_path / "trading_memory.tmp"
        stale_tmp.write_text(
            "GARBAGE CONTENT — should be overwritten", encoding="utf-8"
        )
        log.update_with_outcome("NVDA", "2026-01-10", 0.042, 0.021, 5, "Correct.")
        assert not stale_tmp.exists()
        entries = log.load_entries()
        assert len(entries) == 1
        assert entries[0]["reflection"] == "Correct."
        assert entries[0]["pending"] is False

    def test_update_noop_when_no_log_path(self):
        log = TradingMemoryLog(config=None)
        log.update_with_outcome("NVDA", "2026-01-10", 0.05, 0.02, 5, "Reflection")

    def test_formatting_roundtrip_after_update(self, tmp_path):
        """All fields intact and blank line between tag and DECISION preserved after update."""
        log = make_log(tmp_path)
        log.store_decision("NVDA", "2026-01-10", DECISION_BUY)
        log.update_with_outcome(
            "NVDA", "2026-01-10", 0.042, 0.021, 5, "Momentum confirmed."
        )
        entries = log.load_entries()
        assert len(entries) == 1
        e = entries[0]
        assert e["pending"] is False
        assert e["decision"] == DECISION_BUY.strip()
        assert e["reflection"] == "Momentum confirmed."
        assert e["raw"] == "+4.2%"
        assert e["alpha"] == "+2.1%"
        assert e["holding"] == "5d"
        raw_text = (tmp_path / "trading_memory.md").read_text(encoding="utf-8")
        assert "[2026-01-10 | NVDA | Buy | +4.2% | +2.1% | 5d]\n\nDECISION:" in raw_text

    # Reflector.reflect_on_final_decision

    def test_reflect_on_final_decision_returns_llm_output(self):
        mock_llm = MagicMock()
        mock_llm.invoke.return_value.content = (
            "Directionally correct. Thesis confirmed."
        )
        reflector = Reflector(mock_llm)
        result = reflector.reflect_on_final_decision(
            final_decision=DECISION_BUY, raw_return=0.042, alpha_return=0.021
        )
        assert result == "Directionally correct. Thesis confirmed."
        mock_llm.invoke.assert_called_once()

    def test_reflect_on_final_decision_includes_returns_in_prompt(self):
        """Return figures are present in the human message sent to the LLM."""
        mock_llm = MagicMock()
        mock_llm.invoke.return_value.content = "Incorrect call."
        reflector = Reflector(mock_llm)
        reflector.reflect_on_final_decision(
            final_decision=DECISION_SELL, raw_return=-0.08, alpha_return=-0.05
        )
        messages = mock_llm.invoke.call_args[0][0]
        human_content = next(content for role, content in messages if role == "human")
        assert "-8.0%" in human_content
        assert "-5.0%" in human_content
        assert "Exit position immediately." in human_content

    # TradingAgentsGraph._fetch_returns

    def test_fetch_returns_valid_ticker(self):
        stock_prices = [100.0, 102.0, 104.0, 103.0, 105.0, 106.0]
        spy_prices = [400.0, 402.0, 404.0, 403.0, 405.0, 406.0]
        mock_graph = MagicMock(spec=TradingAgentsGraph)
        with patch("yfinance.Ticker") as mock_ticker_cls:

            def _make_ticker(sym):
                m = MagicMock()
                m.history.return_value = _price_df(
                    spy_prices if sym == "SPY" else stock_prices
                )
                return m

            mock_ticker_cls.side_effect = _make_ticker
            raw, alpha, days = TradingAgentsGraph._fetch_returns(
                mock_graph, "NVDA", "2026-01-05"
            )
        assert raw is not None and alpha is not None and days is not None
        assert (
            isinstance(raw, float)
            and isinstance(alpha, float)
            and isinstance(days, int)
        )
        assert days == 5

    def test_fetch_returns_too_recent(self):
        """Only 1 data point available → returns (None, None, None), no crash."""
        mock_graph = MagicMock(spec=TradingAgentsGraph)
        with patch("yfinance.Ticker") as mock_ticker_cls:
            m = MagicMock()
            m.history.return_value = _price_df([100.0])
            mock_ticker_cls.return_value = m
            raw, alpha, days = TradingAgentsGraph._fetch_returns(
                mock_graph, "NVDA", "2026-04-19"
            )
        assert raw is None and alpha is None and days is None

    def test_fetch_returns_delisted(self):
        """Empty DataFrame → returns (None, None, None), no crash."""
        mock_graph = MagicMock(spec=TradingAgentsGraph)
        with patch("yfinance.Ticker") as mock_ticker_cls:
            m = MagicMock()
            m.history.return_value = pd.DataFrame({"Close": []})
            mock_ticker_cls.return_value = m
            raw, alpha, days = TradingAgentsGraph._fetch_returns(
                mock_graph, "XXXXXFAKE", "2026-01-10"
            )
        assert raw is None and alpha is None and days is None

    def test_fetch_returns_spy_shorter_than_stock(self):
        """SPY having fewer rows than the stock must not raise IndexError."""
        stock_prices = [100.0, 102.0, 104.0, 103.0, 105.0, 106.0]
        spy_prices = [400.0, 402.0, 403.0]
        mock_graph = MagicMock(spec=TradingAgentsGraph)
        with patch("yfinance.Ticker") as mock_ticker_cls:

            def _make_ticker(sym):
                m = MagicMock()
                m.history.return_value = _price_df(
                    spy_prices if sym == "SPY" else stock_prices
                )
                return m

            mock_ticker_cls.side_effect = _make_ticker
            raw, alpha, days = TradingAgentsGraph._fetch_returns(
                mock_graph, "NVDA", "2026-01-05"
            )
        assert raw is not None and alpha is not None and days is not None
        assert days == 2

    # TradingAgentsGraph._resolve_benchmark — picks index for alpha calc

    def test_resolve_benchmark_explicit_override(self):
        """config['benchmark_ticker'] wins for every ticker."""
        mock_graph = MagicMock(spec=TradingAgentsGraph)
        mock_graph.config = {
            "benchmark_ticker": "QQQ",
            "benchmark_map": {"": "SPY", ".T": "^N225"},
        }
        assert TradingAgentsGraph._resolve_benchmark(mock_graph, "7203.T") == "QQQ"
        assert TradingAgentsGraph._resolve_benchmark(mock_graph, "NVDA") == "QQQ"

    def test_resolve_benchmark_suffix_map(self):
        """Known suffixes route to their regional index."""
        mock_graph = MagicMock(spec=TradingAgentsGraph)
        mock_graph.config = {
            "benchmark_ticker": None,
            "benchmark_map": {
                ".T": "^N225",
                ".HK": "^HSI",
                ".NS": "^NSEI",
                ".L": "^FTSE",
                ".TO": "^GSPTSE",
                ".AX": "^AXJO",
                ".BO": "^BSESN",
                "": "SPY",
            },
        }
        assert TradingAgentsGraph._resolve_benchmark(mock_graph, "7203.T") == "^N225"
        assert TradingAgentsGraph._resolve_benchmark(mock_graph, "0700.HK") == "^HSI"
        assert (
            TradingAgentsGraph._resolve_benchmark(mock_graph, "RELIANCE.NS") == "^NSEI"
        )
        assert TradingAgentsGraph._resolve_benchmark(mock_graph, "AZN.L") == "^FTSE"

    def test_resolve_benchmark_china_a_shares(self):
        """A-share tickers route to their exchange composite (uses the real
        default benchmark_map, since A-share support relies on it)."""
        DEFAULT_CONFIG = getattr(
            importlib.import_module("trader.default"), "DEFAULT_CONFIG"
        )
        mock_graph = MagicMock(spec=TradingAgentsGraph)
        mock_graph.config = {
            "benchmark_ticker": None,
            "benchmark_map": DEFAULT_CONFIG["benchmark_map"],
        }
        assert (
            TradingAgentsGraph._resolve_benchmark(mock_graph, "600519.SS")
            == "000001.SS"
        )
        assert (
            TradingAgentsGraph._resolve_benchmark(mock_graph, "000001.SZ")
            == "399001.SZ"
        )

    def test_resolve_benchmark_us_ticker_defaults_to_spy(self):
        """US tickers (no dotted suffix) take the empty-suffix entry."""
        mock_graph = MagicMock(spec=TradingAgentsGraph)
        mock_graph.config = {
            "benchmark_ticker": None,
            "benchmark_map": {"": "SPY", ".T": "^N225"},
        }
        assert TradingAgentsGraph._resolve_benchmark(mock_graph, "NVDA") == "SPY"
        assert TradingAgentsGraph._resolve_benchmark(mock_graph, "AAPL") == "SPY"

    def test_resolve_benchmark_unknown_suffix_falls_back(self):
        """Unrecognised suffix (BRK.B, FAKE.XX) falls back to SPY."""
        mock_graph = MagicMock(spec=TradingAgentsGraph)
        mock_graph.config = {
            "benchmark_ticker": None,
            "benchmark_map": {"": "SPY", ".T": "^N225"},
        }
        assert TradingAgentsGraph._resolve_benchmark(mock_graph, "FAKE.XX") == "SPY"
        assert TradingAgentsGraph._resolve_benchmark(mock_graph, "BRK.B") == "SPY"

    def test_resolve_benchmark_case_insensitive(self):
        """Suffix matching is case-insensitive so 7203.t resolves like 7203.T."""
        mock_graph = MagicMock(spec=TradingAgentsGraph)
        mock_graph.config = {
            "benchmark_ticker": None,
            "benchmark_map": {".T": "^N225", "": "SPY"},
        }
        assert TradingAgentsGraph._resolve_benchmark(mock_graph, "7203.t") == "^N225"

    def test_reflector_includes_benchmark_in_label(self):
        """benchmark_name appears in the prompt label, not 'SPY' hardcoded."""
        mock_llm = MagicMock()
        mock_llm.invoke.return_value.content = "Directionally correct."
        reflector = Reflector(mock_llm)
        reflector.reflect_on_final_decision(
            final_decision=DECISION_BUY,
            raw_return=0.05,
            alpha_return=0.02,
            benchmark_name="^N225",
        )
        messages = mock_llm.invoke.call_args[0][0]
        human_content = next(content for role, content in messages if role == "human")
        assert "Alpha vs ^N225:" in human_content
        assert "Alpha vs SPY:" not in human_content

    def test_reflector_defaults_to_spy_for_unupdated_callers(self):
        """Default benchmark_name keeps the SPY label for legacy callers."""
        mock_llm = MagicMock()
        mock_llm.invoke.return_value.content = "ok"
        reflector = Reflector(mock_llm)
        reflector.reflect_on_final_decision(
            final_decision=DECISION_BUY,
            raw_return=0.05,
            alpha_return=0.02,
        )
        messages = mock_llm.invoke.call_args[0][0]
        human_content = next(content for role, content in messages if role == "human")
        assert "Alpha vs SPY:" in human_content

    # TradingAgentsGraph._resolve_pending_entries

    def test_resolve_skips_other_tickers(self, tmp_path):
        """Pending AAPL entry is not resolved when the run is for NVDA."""
        log = make_log(tmp_path)
        log.store_decision("AAPL", "2026-01-10", DECISION_BUY)
        mock_graph = MagicMock(spec=TradingAgentsGraph)
        mock_graph.memory_log = log
        mock_graph._fetch_returns = MagicMock(return_value=(0.05, 0.02, 5))
        TradingAgentsGraph._resolve_pending_entries(mock_graph, "NVDA")
        mock_graph._fetch_returns.assert_not_called()
        assert len(log.get_pending_entries()) == 1

    def test_resolve_marks_entry_completed(self, tmp_path):
        """After resolve, get_pending_entries() is empty and the entry has a REFLECTION."""
        log = make_log(tmp_path)
        log.store_decision("NVDA", "2026-01-05", DECISION_BUY)
        mock_reflector = MagicMock()
        mock_reflector.reflect_on_final_decision.return_value = "Momentum confirmed."
        mock_graph = MagicMock(spec=TradingAgentsGraph)
        mock_graph.memory_log = log
        mock_graph.reflector = mock_reflector
        mock_graph._fetch_returns = MagicMock(return_value=(0.05, 0.02, 5))
        TradingAgentsGraph._resolve_pending_entries(mock_graph, "NVDA")
        assert log.get_pending_entries() == []
        entries = log.load_entries()
        assert len(entries) == 1
        assert entries[0]["pending"] is False
        assert entries[0]["reflection"] == "Momentum confirmed."
        assert "+5.0%" in entries[0]["raw"]
        assert "+2.0%" in entries[0]["alpha"]


# ---------------------------------------------------------------------------
# Portfolio Manager injection: past_context in state and prompt
# ---------------------------------------------------------------------------


class TestPortfolioManagerInjection:
    # past_context in initial state

    def test_past_context_in_initial_state(self):
        propagator = Propagator()
        state = propagator.create_initial_state(
            "NVDA", "2026-01-10", past_context="some context"
        )
        assert "past_context" in state
        assert state["past_context"] == "some context"

    def test_past_context_defaults_to_empty(self):
        propagator = Propagator()
        state = propagator.create_initial_state("NVDA", "2026-01-10")
        assert state["past_context"] == ""

    # PM prompt

    def test_pm_prompt_includes_past_context(self):
        captured = {}
        llm = _structured_pm_llm(captured)
        pm_node = create_portfolio_manager(llm)
        state = _make_pm_state(
            past_context="[2026-01-05 | NVDA | Buy | +5.0% | +2.0% | 5d]\nGreat call."
        )
        pm_node(state)
        assert "Lessons from prior decisions and outcomes" in captured["prompt"]
        assert "Great call." in captured["prompt"]

    def test_pm_no_past_context_no_section(self):
        """PM prompt omits the lessons section entirely when past_context is empty."""
        captured = {}
        llm = _structured_pm_llm(captured)
        pm_node = create_portfolio_manager(llm)
        state = _make_pm_state(past_context="")
        pm_node(state)
        assert "Lessons from prior decisions" not in captured["prompt"]

    def test_pm_returns_rendered_markdown_with_rating(self):
        """The structured PortfolioDecision is rendered to markdown that
        downstream consumers (memory log, signal processor, CLI display)
        can parse without any extra LLM call."""
        captured = {}
        decision = PortfolioDecision(
            rating=PortfolioRating.OVERWEIGHT,
            executive_summary="Build position gradually over the next two weeks.",
            investment_thesis="AI capex cycle remains intact; institutional flows constructive.",
            price_target=215.0,
            time_horizon="3-6 months",
        )
        llm = _structured_pm_llm(captured, decision)
        pm_node = create_portfolio_manager(llm)
        result = pm_node(_make_pm_state())
        md = result["final_trade_decision"]
        assert "**Rating**: Overweight" in md
        assert "**Executive Summary**: Build position gradually" in md
        assert "**Investment Thesis**: AI capex cycle" in md
        assert "**Price Target**: 215.0" in md
        assert "**Time Horizon**: 3-6 months" in md

    def test_pm_falls_back_to_freetext_when_structured_unavailable(self):
        """If a provider does not support with_structured_output, the agent
        falls back to a plain invoke and returns whatever prose the model
        produced, so the pipeline never blocks."""
        plain_response = "**Rating**: Sell\n\nExit ahead of guidance."
        llm = MagicMock()
        llm.with_structured_output.side_effect = NotImplementedError(
            "provider unsupported"
        )
        llm.invoke.return_value = MagicMock(content=plain_response)
        pm_node = create_portfolio_manager(llm)
        result = pm_node(_make_pm_state())
        assert result["final_trade_decision"] == plain_response

    # get_past_context ordering and limits

    def test_same_ticker_prioritised(self, tmp_path):
        """Same-ticker entries in same-ticker section; cross-ticker entries in cross-ticker section."""
        log = make_log(tmp_path)
        _resolve_entry(log, "NVDA", "2026-01-05", DECISION_BUY, "Momentum confirmed.")
        _resolve_entry(log, "AAPL", "2026-01-06", DECISION_SELL, "Overvalued.")
        result = log.get_past_context("NVDA")
        assert "Past analyses of NVDA" in result
        assert "Recent cross-ticker lessons" in result
        same_block, cross_block = result.split("Recent cross-ticker lessons")
        assert "NVDA" in same_block
        assert "AAPL" in cross_block

    def test_cross_ticker_reflection_only(self, tmp_path):
        """Cross-ticker entries show only the REFLECTION text, not the full DECISION."""
        log = make_log(tmp_path)
        _resolve_entry(
            log, "AAPL", "2026-01-06", DECISION_SELL, "Overvalued correction."
        )
        result = log.get_past_context("NVDA")
        assert "Overvalued correction." in result
        assert "Exit position immediately." not in result

    def test_n_same_limit_respected(self, tmp_path):
        """More than 5 same-ticker completed entries → only 5 injected."""
        log = make_log(tmp_path)
        for i in range(7):
            _resolve_entry(
                log, "NVDA", f"2026-01-{i + 1:02d}", DECISION_BUY, f"Lesson {i}."
            )
        result = log.get_past_context("NVDA", n_same=5)
        lessons_present = sum(1 for i in range(7) if f"Lesson {i}." in result)
        assert lessons_present == 5

    def test_n_cross_limit_respected(self, tmp_path):
        """More than 3 cross-ticker completed entries → only 3 injected."""
        log = make_log(tmp_path)
        tickers = ["AAPL", "MSFT", "TSLA", "AMZN", "GOOG"]
        for i, ticker in enumerate(tickers):
            _resolve_entry(
                log, ticker, f"2026-01-{i + 1:02d}", DECISION_BUY, f"{ticker} lesson."
            )
        result = log.get_past_context("NVDA", n_cross=3)
        cross_count = sum(result.count(f"{t} lesson.") for t in tickers)
        assert cross_count == 3

    # Full A→B→C integration cycle

    def test_full_cycle_store_resolve_inject(self, tmp_path):
        """store pending → resolve with outcome → past_context non-empty for PM."""
        log = make_log(tmp_path)
        log.store_decision("NVDA", "2026-01-05", DECISION_BUY)
        assert len(log.get_pending_entries()) == 1
        assert log.get_past_context("NVDA") == ""
        log.update_with_outcome("NVDA", "2026-01-05", 0.05, 0.02, 5, "Correct call.")
        assert log.get_pending_entries() == []
        past_ctx = log.get_past_context("NVDA")
        assert past_ctx != ""
        assert "NVDA" in past_ctx
        assert "Correct call." in past_ctx
        assert "DECISION:" in past_ctx
        assert "REFLECTION:" in past_ctx


# ---------------------------------------------------------------------------
# CN legacy role memory compatibility
# ---------------------------------------------------------------------------


class TestLegacyMemoryCompatibility:
    def test_financial_situation_memory_preserved(self):
        """CN FinancialSituationMemory remains importable alongside TradingMemoryLog."""
        m = importlib.import_module("trader.agents.utils.memory")
        assert hasattr(m, "FinancialSituationMemory")

    def test_bm25_not_imported(self):
        """rank_bm25 must not be present in the memory module namespace."""
        m = importlib.import_module("trader.agents.utils.memory")
        assert not hasattr(m, "BM25Okapi")

    def test_reflect_and_remember_preserved(self):
        """TradingAgentsGraph still exposes CN role-memory reflection."""
        assert hasattr(TradingAgentsGraph, "reflect_and_remember")

    def test_portfolio_manager_no_memory_param(self):
        """create_portfolio_manager accepts only llm; passing memory= raises TypeError."""
        mock_llm = MagicMock()
        create_portfolio_manager(mock_llm)
        with pytest.raises(TypeError):
            create_portfolio_manager(mock_llm, memory=MagicMock())

    def test_full_pipeline_no_regression(self, tmp_path):
        """propagate() completes and stores the decision after the redesign."""
        functools = importlib.import_module("functools")

        fake_state = {
            "final_trade_decision": "Rating: Buy\nBuy NVDA.",
            "company_of_interest": "NVDA",
            "trade_date": "2026-01-10",
            "market_report": "",
            "sentiment_report": "",
            "news_report": "",
            "fundamentals_report": "",
            "investment_debate_state": {
                "bull_history": "",
                "bear_history": "",
                "history": "",
                "current_response": "",
                "judge_decision": "",
            },
            "investment_plan": "",
            "trader_investment_plan": "",
            "risk_debate_state": {
                "aggressive_history": "",
                "conservative_history": "",
                "neutral_history": "",
                "history": "",
                "judge_decision": "",
                "current_aggressive_response": "",
                "current_conservative_response": "",
                "current_neutral_response": "",
                "count": 1,
                "latest_speaker": "",
            },
        }
        mock_graph = MagicMock()
        mock_graph.memory_log = TradingMemoryLog(
            {"memory_log_path": str(tmp_path / "mem.md")}
        )
        mock_graph.log_states_dict = {}
        mock_graph.debug = False
        mock_graph.config = {"results_dir": str(tmp_path)}
        mock_graph.graph.invoke.return_value = fake_state
        mock_graph.propagator.create_initial_state.return_value = fake_state
        mock_graph.propagator.get_graph_args.return_value = {}
        mock_graph.signal_processor.process_signal.return_value = "Buy"
        # Bind the real _run_graph so propagate's call to self._run_graph executes
        # the actual write path instead of the auto-MagicMock.
        mock_graph._run_graph = functools.partial(
            TradingAgentsGraph._run_graph, mock_graph
        )
        TradingAgentsGraph.propagate(mock_graph, "NVDA", "2026-01-10")
        entries = mock_graph.memory_log.load_entries()
        assert len(entries) == 1
        assert entries[0]["ticker"] == "NVDA"
        assert entries[0]["pending"] is True
