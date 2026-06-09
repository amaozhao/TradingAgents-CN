# Report Detail Readability And I18n Prep Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the Next report detail page readable by replacing internal agent keys with user-facing sections, grouping the report flow, hiding duplicate generated sections, and preparing section labels for future Chinese/English UI switching.

**Architecture:** Keep backend report data unchanged and add a small frontend presentation layer for report section metadata, ordering, grouping, and duplicate aliases. `ReportDetailPage` will render grouped report sections from that metadata rather than directly mapping raw object keys. The Vue frontend is out of scope.

**Tech Stack:** Next.js, React 19, TypeScript, Vitest, Testing Library, existing shadcn-style UI components.

---

### Task 1: Add Regression Tests For Report Section Presentation

**Files:**
- Create: `frontend/tests/components/report-detail-page.test.tsx`
- Modify: none

- [ ] **Step 1: Write the failing test**

Create `frontend/tests/components/report-detail-page.test.tsx` with tests that mock `fetchReportDetail`, render `ReportDetailPage`, and assert:
- internal keys such as `safe_analyst` and `risk_management_decision` are not visible as headings
- user-facing Chinese titles such as `保守风险分析师` and `风控委员会决议` are visible
- duplicate alias content is not rendered twice
- major groups such as `总览`, `核心报告`, `多方辩论`, `风险评审`, and `决策链路` are visible

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
cd frontend && pnpm vitest run tests/components/report-detail-page.test.tsx
```

Expected: FAIL because the current page renders raw keys and has no grouping metadata.

### Task 2: Add Report Section Metadata

**Files:**
- Create: `frontend/features/reports/report-section-meta.ts`
- Test: `frontend/tests/components/report-detail-page.test.tsx`

- [ ] **Step 1: Implement metadata**

Create metadata for known report keys:
- `safe_analyst`
- `risky_analyst`
- `neutral_analyst`
- `bear_researcher`
- `bull_researcher`
- `investment_plan`
- `research_team_decision`
- `trader_investment_plan`
- `risk_management_decision`
- `final_trade_decision`
- existing core keys such as `market_report`, `fundamentals_report`, `news_report`, `sentiment_report`

Each entry must include `key`, `group`, `order`, `zhTitle`, `enTitle`, `description`, and optional `aliasOf`.

- [ ] **Step 2: Add ordering and dedupe helpers**

Export helper functions:
- `getReportSectionMeta(key)`
- `buildReportSectionGroups(reports)`

`buildReportSectionGroups` must:
- keep known sections in business order
- hide raw duplicate aliases when their canonical section exists
- put unknown sections in an `原始内容` group with a cleaned fallback title

### Task 3: Render Grouped Report Detail UI

**Files:**
- Modify: `frontend/features/reports/report-detail-page.tsx`
- Test: `frontend/tests/components/report-detail-page.test.tsx`

- [ ] **Step 1: Replace raw object mapping**

Update `ReportDetailPage` to use `buildReportSectionGroups(report.reports || {})` and render groups with section cards.

- [ ] **Step 2: Improve summary and decision hierarchy**

Keep the top metrics. Add grouped bands:
- `总览`: report summary and final trade decision when available
- `核心报告`: market/fundamentals/news/sentiment
- `多方辩论`: bull/bear researchers
- `风险评审`: safe/neutral/risky analysts
- `决策链路`: research team decision, trader investment plan, risk committee decision
- `原始内容`: unknown sections only

- [ ] **Step 3: Keep i18n prep lightweight**

Use `zhTitle` now, but keep metadata with `enTitle` and title access through one helper so a later language switch can change labels without rewriting page layout.

### Task 4: Verify Frontend Quality Gates

**Files:**
- Modified files from previous tasks

- [ ] **Step 1: Run focused component test**

```bash
cd frontend && pnpm vitest run tests/components/report-detail-page.test.tsx
```

Expected: PASS.

- [ ] **Step 2: Run related frontend tests**

```bash
cd frontend && pnpm vitest run tests/components/report-detail-page.test.tsx tests/routes/route-config.test.ts tests/e2e/reports.spec.ts
```

If the e2e spec cannot run under Vitest because it is Playwright-only, run the component and route tests under Vitest and skip Playwright with an explicit note.

- [ ] **Step 3: Run type check**

```bash
cd frontend && pnpm type-check
```

Expected: no TypeScript errors from the changed files.

