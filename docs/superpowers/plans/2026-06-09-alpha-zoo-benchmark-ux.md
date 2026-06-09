# Alpha Zoo Benchmark UX Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Alpha factor detail benchmark navigation and benchmark results understandable without implying that the current backend performs returns backtesting.

**Architecture:** Keep the change in the Next frontend. The detail page passes `alpha_id` to the benchmark page, where the current factor is preselected in a multi-select factor list. The benchmark page chooses `/api/alpha-zoo/bench` only when exactly one factor is explicitly selected; otherwise it calls `/api/alpha-zoo/compare` for selected factors or the whole zoo. The UI labels the current result as an output coverage check, not an investment performance backtest.

**Tech Stack:** Next.js 16, React 19, TypeScript, Vitest, existing Alpha Zoo REST API.

---

## Spec

### Problem

The Alpha factor detail page currently links to `/alpha-zoo/bench?zoo=<zoo>`. That route loads every factor in the zoo and runs the compare endpoint, so a user starting from `academic_carhart_mom` is taken to a batch test for all academic factors instead of the selected factor.

The benchmark result table exposes backend implementation fields (`rows`, `columns`, `non_null_values`) with no explanation. The backend currently builds a synthetic panel and reports factor output coverage only. It does not calculate returns, IC, Sharpe, drawdown, or other investment performance metrics.

### Non-Goals

- Do not modify `frontend-vue`.
- Do not implement a real factor returns backtest in this pass.
- Do not change backend job execution semantics in this pass.
- Do not hide the current backend limitation; the UI must state it plainly.

### Requirements

- From a detail page, the benchmark button must navigate with the selected factor id: `/alpha-zoo/bench?alpha_id=<factor_id>&zoo=<zoo>`.
- The benchmark page must support a selectable factor list:
  - `alpha_id` from the detail page must preselect that factor.
  - Users must choose factors with checkboxes, not by manually typing factor IDs.
  - The old target-factor text input and its helper text must not appear.
- With exactly one selected factor, `Run` must call `alphaZooApi.bench`.
- With multiple selected factors, `Run` must call `alphaZooApi.compare`.
- With no selected factors, `Run` must batch-check all factors in the selected zoo via `alphaZooApi.compare`.
- Result labels must use user-facing terms:
  - `有效日期数` / `Valid dates` for backend `rows`.
  - `股票数量` / `Symbols` for backend `columns`.
  - `有效因子值` / `Valid values` for backend `non_null_values`.
  - `覆盖率` / `Coverage` as `non_null_values / (rows * columns)`.
  - `可计算` / `Computable` when valid values are greater than zero; otherwise `无有效输出` / `No valid output`.
- The benchmark page must show an explanatory notice that the current page checks factor output coverage on backend test data and is not a returns backtest.
- The default date range must be long enough for 252-day warm-up factors; otherwise academic momentum factors will always show no valid output.
- Empty results and invalid/missing factors must keep the page stable and show the existing error area.

### Acceptance Criteria

- `AlphaFactorDetailPage` renders a benchmark link containing both `alpha_id` and `zoo`.
- `AlphaBenchPage` initialized with `alpha_id=academic_carhart_mom&zoo=academic` shows single-factor mode and a checked `academic_carhart_mom` checkbox.
- The benchmark controls do not show a `目标因子` text input or helper text under it.
- Running single-factor mode posts to `alphaZooApi.bench` and does not call `alphaZooApi.compare`.
- Running multiple selected factors posts those selected factor IDs to `alphaZooApi.compare`.
- Running with no selected factors posts all current-zoo factor IDs to `alphaZooApi.compare`.
- A bench result with `rows=360`, `columns=3`, `non_null_values=324` displays `30.0%`.
- The result table no longer shows raw headers `结果行数`, `列数`, `非空值` without explanation.
- `pnpm lint`, targeted tests, `pnpm type-check`, full `pnpm test`, and `pnpm build` pass in `frontend`.

## Implementation Plan

### Task 1: Lock Detail-Page Navigation

**Files:**
- Modify: `frontend/tests/components/alpha-zoo-page.test.tsx`
- Modify: `frontend/features/alpha-zoo/alpha-factor-detail-page.tsx`

- [ ] **Step 1: Update the failing test**

Change the detail page test to expect:

```ts
expect(screen.getByRole("link", { name: "运行该因子测试" })).toHaveAttribute(
  "href",
  "/alpha-zoo/bench?alpha_id=alpha101_001&zoo=alpha101"
)
```

- [ ] **Step 2: Run the test and verify failure**

Run:

```bash
cd frontend && pnpm test tests/components/alpha-zoo-page.test.tsx -- --runInBand
```

Expected: failure because the current link is `/alpha-zoo/bench?zoo=alpha101`.

- [ ] **Step 3: Update the detail page link and label**

In `AlphaFactorDetailPage`, change the Chinese copy to `运行该因子测试`, English copy to `Run this factor`, and build the URL with `alpha_id` plus `zoo`.

- [ ] **Step 4: Run the test and verify pass**

Run:

```bash
cd frontend && pnpm test tests/components/alpha-zoo-page.test.tsx -- --runInBand
```

Expected: all tests in the file pass.

### Task 2: Add Benchmark-Page Factor Selection Semantics

**Files:**
- Modify: `frontend/features/alpha-zoo/alpha-bench-page.tsx`
- Modify: `frontend/tests/components/alpha-zoo-page.test.tsx`

- [ ] **Step 1: Add tests for selected-factor execution**

Mock `useSearchParams` in the component test so the benchmark page can be rendered with `alpha_id=alpha101_001&zoo=alpha101`.

Add one test where clicking run calls:

```ts
alphaZooApi.bench({
  alpha_id: "alpha101_001",
  symbols: ["600519", "000001", "300750"],
      start_date: "2025-01-01",
      end_date: "2026-06-03"
})
```

Add one test where the target factor input is cleared and clicking run calls `alphaZooApi.compare`.

Revise this to the final UI behavior: no target-factor input exists. The page renders factor checkboxes, the URL `alpha_id` preselects one checkbox, multiple checked boxes call `alphaZooApi.compare`, and no checked boxes mean "run the current zoo".

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
cd frontend && pnpm test tests/components/alpha-zoo-page.test.tsx -- --runInBand
```

Expected: failure because the benchmark page does not yet render a checkbox-based factor selector.

- [ ] **Step 3: Implement selected factor state and run branching**

In `AlphaBenchPage`:

- Initialize `selectedIds` from `searchParams.get("alpha_id")`.
- Keep `zoo` initialization from `searchParams.get("zoo")`.
- Render the loaded factors as checkboxes.
- If exactly one factor is selected, call `alphaZooApi.bench`.
- If multiple factors are selected, call `alphaZooApi.compare` with the selected IDs.
- If no factors are selected, call `alphaZooApi.compare` with all currently loaded zoo factors.

- [ ] **Step 4: Run tests and verify pass**

Run:

```bash
cd frontend && pnpm test tests/components/alpha-zoo-page.test.tsx -- --runInBand
```

Expected: all tests in the file pass.

### Task 3: Make Coverage Results Understandable

**Files:**
- Modify: `frontend/features/alpha-zoo/alpha-bench-page.tsx`
- Modify: `frontend/tests/components/alpha-zoo-page.test.tsx`

- [ ] **Step 1: Add tests for normalized result labels**

Add a benchmark result fixture:

```ts
{
  result: {
    kind: "alpha_bench",
    alpha_id: "alpha101_001",
    summary: {
      factor_id: "alpha101_001",
      rows: 360,
      columns: 3,
      non_null_values: 324
    },
    classification: "alive"
  }
}
```

Assert that the page displays `有效日期数`, `股票数量`, `有效因子值`, `覆盖率`, `30.0%`, and an explanatory coverage notice.

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
cd frontend && pnpm test tests/components/alpha-zoo-page.test.tsx -- --runInBand
```

Expected: failure because the current page only shows raw coverage fields.

- [ ] **Step 3: Implement result normalization**

Add helpers in `AlphaBenchPage`:

```ts
function coverageRate(row: ResultRow) {
  const denominator = (row.rows || 0) * (row.columns || 0)
  return denominator > 0 && typeof row.non_null_values === "number"
    ? row.non_null_values / denominator
    : null
}

function formatPercent(value: number | null) {
  return value === null ? "-" : `${(value * 100).toFixed(1)}%`
}
```

Normalize both single bench `result.summary` and batch compare `result.rows` into one table shape.

- [ ] **Step 4: Update table headers and explanatory copy**

Use the translated labels from the spec and add a notice above the controls explaining that this is a coverage check, not a returns backtest.

- [ ] **Step 5: Run tests and verify pass**

Run:

```bash
cd frontend && pnpm test tests/components/alpha-zoo-page.test.tsx -- --runInBand
```

Expected: all tests in the file pass.

### Task 4: Verify and Live-Check

**Files:**
- Verify only.

- [ ] **Step 1: Run quality gates**

Run:

```bash
cd frontend && pnpm lint
cd frontend && pnpm type-check
cd frontend && pnpm test
cd frontend && pnpm build
```

Expected: all pass.

- [ ] **Step 2: Live-check Next pages**

With backend and Next running, open:

```text
http://127.0.0.1:3000/alpha-zoo/academic_carhart_mom
http://127.0.0.1:3000/alpha-zoo/bench?alpha_id=academic_carhart_mom&zoo=academic
```

Expected:

- Detail page button points to the single-factor benchmark URL.
- Benchmark page shows target factor `academic_carhart_mom`.
- The explanatory notice is visible.
- Results, after running, use `有效日期数`, `股票数量`, `有效因子值`, and `覆盖率`.

## Risks and Mitigations

- **Risk:** Users may still expect investment performance metrics from the word benchmark.  
  **Mitigation:** Use copy that says coverage check and explicitly says it is not a returns backtest.

- **Risk:** Batch mode and single mode could call the wrong endpoint.  
  **Mitigation:** Test both run paths against mocked `alphaZooApi.bench` and `alphaZooApi.compare`.

- **Risk:** Backend result shapes differ between single and compare jobs.  
  **Mitigation:** Normalize `result.summary` and `result.rows` into one table shape before rendering.

- **Risk:** React 19 lint rules reject synchronous state updates in effects.  
  **Mitigation:** Keep effect-triggered state updates in async callbacks or microtasks, matching the current Alpha Zoo lint fix pattern.

## Self-Review

- Spec coverage: Each requirement maps to Task 1, Task 2, Task 3, or Task 4.
- Placeholder scan: No `TBD`, `TODO`, or unspecified implementation steps remain.
- Type consistency: `alpha_id`, `zoo`, `rows`, `columns`, and `non_null_values` match the frontend API types and backend result payloads.
