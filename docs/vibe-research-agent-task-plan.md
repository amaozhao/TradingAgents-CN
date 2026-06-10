# Vibe Research Agent Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a TradingAgents-CN-native global research workspace with Agent, Alpha Zoo, correlation matrix, persisted artifacts, and strict user isolation.

**Architecture:** TradingAgents-CN remains the product shell and source of truth for auth, reports, model config, data services, and frontend routing. Vibe-Trading contributes selected Agent-loop behavior and factor/matrix logic, but unsafe local tools, prompts, caches, and sidecar runtime assumptions are excluded. Phase 0 fixes existing ownership and admin-permission gaps before adding new research surfaces.

**Tech Stack:** FastAPI, existing TradingAgents-CN auth dependencies, existing document/SQL storage strategy, Redis for existing queue and selected research job dispatch, pytest, ruff, pyright, Next.js, React, TanStack Query, Vitest, Playwright, ECharts.

---

## Scope

This plan implements the spec in `docs/vibe-research-agent-spec.md` and expands
the architecture review in `docs/vibe-research-agent-integration-plan.md`.

The plan is intentionally sequenced:

1. Safety and ownership foundation.
2. Research sessions/events/artifacts.
3. Research tool registry.
4. Agent loop.
5. Alpha factor core and panel loader.
6. Alpha jobs and APIs.
7. Correlation jobs and APIs.
8. Frontend pages.
9. End-to-end report synthesis and verification.

Do not start feature UI work before Phase 0 tests pass.

## Commit Protocol For Every Task

Every commit in this plan must follow the workspace Lore protocol. Do not use
one-line `git commit -m` messages. For each Commit step, first write
`/tmp/tradingagents-lore-commit.txt` with this structure, then run
`git commit -F /tmp/tradingagents-lore-commit.txt`:

```text
<why this task was implemented>

<short context paragraph explaining constraints and approach>

Constraint: TradingAgents-CN AGENTS.md requires Lore commit messages
Confidence: medium
Scope-risk: narrow|moderate|broad
Directive: Preserve user isolation and run the listed verification before extending this area
Tested: <exact command run>
Not-tested: <known verification gap, or none>
```

## File Map

Backend files to modify:

- `backend/app/routers/reports.py`: add user-scoped report queries and admin
  exceptions.
- `backend/app/services/analysis/simple/reports.py`: persist `user_id` in
  document-style analysis reports.
- `backend/app/routers/analysis/single.py`: scope task-status recovery.
- `backend/app/routers/analysis/result.py`: scope task-result fallback recovery.
- `backend/app/routers/analysis/setup.py`: add user-aware task/report read
  helpers.
- `backend/app/services/analysis/simple/status.py`: add user-aware status
  lookup or ownership guard.
- `backend/app/routers/config/llm.py`: require admin for global LLM mutations.
- `backend/app/routers/config/providers.py`: require admin for global provider
  mutations.
- `backend/app/routers/config/legacy.py`: require admin for compatibility
  `POST /api/config/llm` global LLM config mutation.
- `backend/app/routers/config/catalog.py`: require admin for compatibility
  `POST /api/config/default/llm` default model mutation.
- `backend/app/main/imports.py`: import new `research_agent`, `alpha_zoo`, and
  `research_matrix` routers after they exist.
- `backend/app/main/application.py`: include new routers with the correct API
  prefixes after they exist.

Backend files to create:

- `backend/app/services/research/agent/context.py`
- `backend/app/services/research/agent/permissions.py`
- `backend/app/services/research/agent/models.py`
- `backend/app/services/research/agent/sessions.py`
- `backend/app/services/research/agent/events.py`
- `backend/app/services/research/agent/artifacts.py`
- `backend/app/services/research/agent/jobs.py`
- `backend/app/services/research/agent/registry.py`
- `backend/app/services/research/agent/loop.py`
- `backend/app/services/research/agent/user/model/keys.py`
- `backend/app/services/research/agent/tools/analysis.py`
- `backend/app/services/research/agent/tools/market/data.py`
- `backend/app/services/research/agent/tools/reports.py`
- `backend/app/services/research/agent/tools/screening.py`
- `backend/app/services/research/agent/tools/alpha.py`
- `backend/app/services/research/agent/tools/correlation.py`
- `backend/app/routers/research/agent.py`
- `backend/app/routers/alpha/zoo.py`
- `backend/app/routers/research/matrix.py`
- `backend/app/services/alpha/zoo/schemas.py`
- `backend/app/services/alpha/zoo/service.py`
- `backend/app/services/alpha/zoo/jobs.py`
- `backend/trader/factors/base.py`
- `backend/trader/factors/registry.py`
- `backend/trader/factors/factor/analysis/core.py`
- `backend/trader/factors/bench/runner.py`
- `backend/trader/factors/compare/runner.py`
- `backend/trader/factors/panel/loader.py`
- `backend/trader/factors/zoo/alpha101/`
- `backend/trader/factors/zoo/gtja191/`
- `backend/trader/factors/zoo/qlib158/`

Backend tests to create:

- `backend/tests/regression/reports/user/isolation/test.py`
- `backend/tests/regression/analysis/user/isolation/test.py`
- `backend/tests/regression/config/admin/test.py`
- `backend/tests/regression/research/agent/permissions/test.py`
- `backend/tests/regression/research/agent/sessions/events/test.py`
- `backend/tests/regression/research/agent/tool/registry/test.py`
- `backend/tests/regression/research/agent/user/model/keys/test.py`
- `backend/tests/regression/research/agent/agent/loop/test.py`
- `backend/tests/regression/research/agent/jobs/test.py`
- `backend/tests/regression/research/agent/report/synthesis/test.py`
- `backend/tests/regression/alpha/zoo/factor/registry/test.py`
- `backend/tests/regression/alpha/zoo/panel/loader/test.py`
- `backend/tests/regression/alpha/zoo/jobs/scope/test.py`
- `backend/tests/regression/research/matrix/jobs/scope/test.py`

The `backend/pyproject.toml` and `backend/tests/pytest.ini` files currently set
`python_files = ["test.py"]`. New backend regression tests must therefore use a
directory-specific `test.py` file, not `test_*.py`, so `conda run -n trader
pytest` collects them in the full suite.

Frontend files to create:

- `frontend/app/agent/page.tsx`
- `frontend/app/agent/loading.tsx`
- `frontend/app/alpha-zoo/page.tsx`
- `frontend/app/alpha-zoo/loading.tsx`
- `frontend/app/correlation/page.tsx`
- `frontend/app/correlation/loading.tsx`
- `frontend/features/research-agent/research-agent-page.tsx`
- `frontend/features/research-agent/session-sidebar.tsx`
- `frontend/features/research-agent/message-timeline.tsx`
- `frontend/features/research-agent/tool-timeline.tsx`
- `frontend/features/research-agent/artifact-drawer.tsx`
- `frontend/features/alpha-zoo/alpha-zoo-page.tsx`
- `frontend/features/alpha-zoo/alpha-factor-table.tsx`
- `frontend/features/alpha-zoo/alpha-bench-runner.tsx`
- `frontend/features/research-matrix/correlation-page.tsx`
- `frontend/features/research-matrix/correlation-heatmap.tsx`
- `frontend/libs/api/research-agent.ts`
- `frontend/libs/api/alpha-zoo.ts`
- `frontend/libs/api/research-matrix.ts`
- `frontend/libs/routes/route-config.ts`

Frontend tests to create:

- `frontend/tests/components/research-agent-page.test.tsx`
- `frontend/tests/components/alpha-zoo-page.test.tsx`
- `frontend/tests/components/correlation-page.test.tsx`
- `frontend/tests/e2e/research-workflow.spec.ts`

Frontend tests to update:

- `frontend/tests/routes/page-loading.test.ts`
- `frontend/tests/routes/route-config.test.ts`

Every new `page.tsx` route needs a sibling `loading.tsx`, and every new product
route must be represented in `frontend/libs/routes/route-config.ts` so the
existing route tests remain valid.

## Task 1: Lock Existing Report Ownership Behavior With Failing Tests

**Files:**

- Create: `backend/tests/regression/reports/user/isolation/test.py`
- Modify after tests fail: `backend/app/routers/reports.py`
- Modify after tests fail: `backend/app/services/analysis/simple/reports.py`

- [ ] **Step 1: Write failing tests for report list/detail/content/download/delete scope**

Create tests that insert two report documents with different `user_id` values
and override `get_current_user` so the route runs as user A. The tests must
assert user B's report is not returned from list and returns `404` from detail,
content, download, and delete routes.

Use this test shape:

```python
import pytest
from fastapi import HTTPException

from app.routers import reports as reports_router


USER_A = {"id": "user-a", "username": "alice", "is_admin": False, "roles": []}
USER_B = {"id": "user-b", "username": "bob", "is_admin": False, "roles": []}


def _matches_query(document: dict, query: dict) -> bool:
    if not query:
        return True
    if "$and" in query:
        return all(_matches_query(document, item) for item in query["$and"])
    if "$or" in query:
        return any(_matches_query(document, item) for item in query["$or"])
    for key, expected in query.items():
        if isinstance(expected, dict) and "$regex" in expected:
            if expected["$regex"].lower() not in str(document.get(key, "")).lower():
                return False
            continue
        if document.get(key) != expected:
            return False
    return True


class FakeCursor:
    def __init__(self, documents: list[dict]):
        self._documents = documents

    def sort(self, *_args):
        return self

    async def to_list(self, _length):
        return self._documents


class FakeReportCollection:
    def __init__(self, documents: list[dict]):
        self.documents = documents
        self.last_find_query = None

    def find(self, query: dict):
        self.last_find_query = query
        return FakeCursor([doc for doc in self.documents if _matches_query(doc, query)])

    async def find_one(self, query: dict, *_args):
        self.last_find_query = query
        for doc in self.documents:
            if _matches_query(doc, query):
                return doc
        return None

    async def delete_one(self, query: dict):
        self.last_find_query = query
        before = len(self.documents)
        self.documents = [doc for doc in self.documents if not _matches_query(doc, query)]
        return type("DeleteResult", (), {"deleted_count": before - len(self.documents)})()


class FakeReportDb:
    def __init__(self, documents: list[dict]):
        self.analysis_reports = FakeReportCollection(documents)


def make_fake_report_db(documents: list[dict]) -> FakeReportDb:
    return FakeReportDb(documents)


@pytest.mark.asyncio
async def test_report_list_returns_only_current_user_reports(monkeypatch):
    fake_reports = [
        {
            "_id": "report-a",
            "analysis_id": "analysis-a",
            "task_id": "task-a",
            "user_id": USER_A["id"],
            "stock_symbol": "300750.SZ",
            "stock_name": "宁德时代",
            "summary": "user a report",
            "reports": {"summary": "a"},
            "created_at": "2026-06-08T00:00:00",
        },
        {
            "_id": "report-b",
            "analysis_id": "analysis-b",
            "task_id": "task-b",
            "user_id": USER_B["id"],
            "stock_symbol": "002594.SZ",
            "stock_name": "比亚迪",
            "summary": "user b report",
            "reports": {"summary": "b"},
            "created_at": "2026-06-08T00:00:00",
        },
    ]

    # Patch get_postgres_db with the existing fake collection helper used in
    # neighboring regression tests, or create a small async fake that records
    # the query and returns only matching documents.
    db = make_fake_report_db(fake_reports)
    monkeypatch.setattr(reports_router, "get_postgres_db", lambda: db)

    response = await reports_router.get_reports_list(user=USER_A)

    assert response["success"] is True
    ids = {item["analysis_id"] for item in response["data"]["reports"]}
    assert ids == {"analysis-a"}
    assert db.analysis_reports.last_find_query["user_id"] == USER_A["id"]
```

- [ ] **Step 2: Run the scoped failing tests**

Run:

```bash
cd backend
conda run -n trader pytest tests/regression/reports/user/isolation/test.py -q
```

Expected before implementation: at least one test fails because report queries
do not enforce `user_id`.

- [ ] **Step 3: Implement user-scoped report query helpers**

In `backend/app/routers/reports.py`, add helpers equivalent to:

```python
def _current_user_id(user: dict) -> str:
    return str(user.get("id") or "")


def _is_admin_user(user: dict) -> bool:
    return bool(user.get("is_admin")) or "admin" in set(user.get("roles") or [])


def _scope_private_report_query(query: dict, user: dict) -> dict:
    if _is_admin_user(user):
        return query
    scoped_query = {"$and": [query, {"user_id": _current_user_id(user)}]}
    if not query:
        scoped_query = {"user_id": _current_user_id(user)}
    return scoped_query
```

Apply `_scope_private_report_query` to list, detail, content, download, and
delete paths. For fallback reads from `analysis_tasks`, require the task owner
to match before reconstructing a report response.

- [ ] **Step 4: Persist report owner during save**

In `backend/app/services/analysis/simple/reports.py`, ensure the document built
inside `_save_analysis_result_web_style` includes a `user_id`. Prefer the task's
owner if the result payload does not contain one:

```python
task_doc = None
try:
    db = get_postgres_db()
    task_doc = await db.analysis_tasks.find_one(
        {"task_id": task_id},
        {"user_id": 1, "user": 1},
    )
except Exception as exc:
    logger.warning("无法从analysis_tasks解析报告归属 task_id=%s: %s", task_id, exc)

owner_id = (
    result.get("user_id")
    or result.get("user")
    or (task_doc or {}).get("user_id")
    or (task_doc or {}).get("user")
)
if owner_id:
    document["user_id"] = str(owner_id)
```

If the save path cannot resolve an owner, log a warning and keep the report
private by preventing it from appearing in normal user report lists until the
owner is backfilled.

- [ ] **Step 5: Run report isolation tests**

Run:

```bash
cd backend
conda run -n trader pytest tests/regression/reports/user/isolation/test.py -q
```

Expected after implementation: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add backend/app/routers/reports.py backend/app/services/analysis/simple/reports.py backend/tests/regression/reports/user/isolation/test.py
git commit -F /tmp/tradingagents-lore-commit.txt
```

## Task 2: Lock Task Status And Result Recovery Ownership

**Files:**

- Create: `backend/tests/regression/analysis/user/isolation/test.py`
- Modify: `backend/app/routers/analysis/single.py`
- Modify: `backend/app/routers/analysis/result.py`
- Modify: `backend/app/routers/analysis/setup.py`
- Modify: `backend/app/services/analysis/simple/status.py`

- [ ] **Step 1: Write failing tests for task status recovery**

Create tests where user A requests user B's `task_id`. Cover memory status,
`analysis_tasks` fallback, and `analysis_reports` fallback.

Core assertion:

```python
with pytest.raises(HTTPException) as exc:
    await single_router.get_task_status_new("task-b", user=USER_A)
assert exc.value.status_code == 404
```

- [ ] **Step 2: Run failing tests**

```bash
cd backend
conda run -n trader pytest tests/regression/analysis/user/isolation/test.py -q
```

Expected before implementation: at least one path returns user B's task or
report data.

- [ ] **Step 3: Make read helpers user-aware**

Change helper signatures in `backend/app/routers/analysis/setup.py`:

```python
async def _get_analysis_task_for_read(
    task_id: str, user_id: str | None = None
) -> Optional[Dict[str, Any]]:
    ...


async def _get_analysis_report_by_task_id_for_read(
    task_id: str, user_id: str | None = None
) -> Optional[Dict[str, Any]]:
    ...
```

When `user_id` is provided, include it in document-store query filters and
verify the owner after SQL read helpers return a document.

- [ ] **Step 4: Scope memory status lookup**

Update `backend/app/services/analysis/simple/status.py` so
`get_task_status(task_id, user_id=None)` checks the owner field when `user_id`
is provided:

```python
owner = result.get("user_id") or result.get("user")
if user_id is not None and str(owner) != str(user_id):
    return None
```

- [ ] **Step 5: Use user-aware helpers in routers**

In `single.py` and `result.py`, pass `user["id"]` into status and fallback read
calls. Return `404` when a task/report exists but does not belong to the user.

- [ ] **Step 6: Run task status tests**

```bash
cd backend
conda run -n trader pytest tests/regression/analysis/user/isolation/test.py -q
```

Expected: all task ownership tests pass.

- [ ] **Step 7: Commit**

```bash
git add backend/app/routers/analysis/single.py backend/app/routers/analysis/result.py backend/app/routers/analysis/setup.py backend/app/services/analysis/simple/status.py backend/tests/regression/analysis/user/isolation/test.py
git commit -F /tmp/tradingagents-lore-commit.txt
```

## Task 3: Add Admin Gates For Global LLM And Provider Mutations

**Files:**

- Create: `backend/tests/regression/config/admin/test.py`
- Modify: `backend/app/routers/config/llm.py`
- Modify: `backend/app/routers/config/providers.py`
- Modify: `backend/app/routers/config/legacy.py`
- Modify: `backend/app/routers/config/catalog.py`

- [ ] **Step 1: Write failing admin-permission tests**

Test non-admin denial and admin success for:

- `DELETE /llm/{provider}/{model_name}`
- `POST /llm/set-default`
- `POST /llm/providers`
- `PUT /llm/providers/{provider_id}`
- `DELETE /llm/providers/{provider_id}`
- `PATCH /llm/providers/{provider_id}/toggle`
- `POST /llm/providers/{provider_id}/fetch-models`
- `POST /llm/providers/migrate-env`
- compatibility `POST /llm` in `backend/app/routers/config/legacy.py`;
- compatibility `POST /default/llm` in `backend/app/routers/config/catalog.py`.

Expected non-admin behavior:

```python
with pytest.raises(HTTPException) as exc:
    await llm_router.set_default_llm_legacy(request, current_user=USER_A)
assert exc.value.status_code == 403
```

- [ ] **Step 2: Run failing admin tests**

```bash
cd backend
conda run -n trader pytest tests/regression/config/admin/test.py -q
```

Expected before implementation: non-admin users can call at least one mutating
route.

- [ ] **Step 3: Add shared admin guard**

Add a local guard or shared helper:

```python
def require_admin_user(current_user: dict | User) -> None:
    is_admin = bool(
        getattr(current_user, "is_admin", False)
        if not isinstance(current_user, dict)
        else current_user.get("is_admin")
    )
    roles = (
        getattr(current_user, "roles", [])
        if not isinstance(current_user, dict)
        else current_user.get("roles", [])
    )
    if not is_admin and "admin" not in set(roles or []):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要管理员权限")
```

Call it at the start of every global mutating config route, including
compatibility routes in `legacy.py` and `catalog.py`. Keep read-only
`GET /api/config/llm`, model catalog reads, and provider catalog reads available
to authenticated users with sanitized output.

- [ ] **Step 4: Run admin tests**

```bash
cd backend
conda run -n trader pytest tests/regression/config/admin/test.py -q
```

Expected: non-admin mutation denied, admin mutation reaches service mock.

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/config/llm.py backend/app/routers/config/providers.py backend/app/routers/config/legacy.py backend/app/routers/config/catalog.py backend/tests/regression/config/admin/test.py
git commit -F /tmp/tradingagents-lore-commit.txt
```

## Task 4: Add Private User Model Key Storage

**Files:**

- Create: `backend/app/services/research/agent/user/model/keys.py`
- Create: `backend/app/routers/user/model/keys.py`
- Create: `backend/tests/regression/research/agent/user/model/keys/test.py`
- Modify: `backend/app/main/imports.py`
- Modify: `backend/app/main/application.py`

- [ ] **Step 1: Write failing user-key isolation and redaction tests**

Test:

- user A can create a private model key record;
- list responses return metadata and a redacted key, never plaintext;
- user A cannot list, read, update, or delete user B's key;
- audit event payloads do not include plaintext `api_key`;
- admin global provider config remains separate from user-owned key storage.

Use this assertion shape:

```python
created = await service.create_key(
    user_id="user-a",
    provider="minimax-token-plan",
    model="MiniMax-M2",
    api_key="sk-real-private-key",
)
listed = await service.list_keys(user_id="user-a")

assert listed[0]["provider"] == "minimax-token-plan"
assert listed[0]["api_key"] == "****"
assert "sk-real-private-key" not in str(listed[0])
```

- [ ] **Step 2: Run failing user-key tests**

```bash
cd backend
conda run -n trader pytest tests/regression/research/agent/user/model/keys/test.py -q
```

Expected before implementation: service/router does not exist.

- [ ] **Step 3: Implement private key service**

Implement owner-scoped CRUD:

```text
create_key(user_id, provider, model, api_key, display_name)
list_keys(user_id)
get_key(user_id, key_id)
update_key(user_id, key_id, api_key | display_name | enabled)
delete_key(user_id, key_id)
resolve_key_for_agent(user_id, provider, model)
```

Store encrypted or otherwise secret-safe key material according to the existing
TradingAgents-CN secret-storage pattern. If the repo does not yet have a
dedicated encryption helper, this task must add one before storing plaintext in
persistent storage.

- [ ] **Step 4: Implement user-owned key routes**

Add routes under `/api/user-model-keys`:

```text
POST   /api/user-model-keys
GET    /api/user-model-keys
GET    /api/user-model-keys/{key_id}
PUT    /api/user-model-keys/{key_id}
DELETE /api/user-model-keys/{key_id}
```

All responses must redact secrets. All lookups must include current
`user_id`.

- [ ] **Step 5: Register router**

Import `user_model_keys` in `backend/app/main/imports.py` and include it in
`backend/app/main/application.py`:

```python
app.include_router(user_model_keys.router, prefix="/api", tags=["user-model-keys"])
```

- [ ] **Step 6: Run user-key tests**

```bash
cd backend
conda run -n trader pytest tests/regression/research/agent/user/model/keys/test.py -q
```

Expected: user-owned key storage, redaction, and isolation tests pass.

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/research/agent/user/model/keys.py backend/app/routers/user/model/keys.py backend/app/main/imports.py backend/app/main/application.py backend/tests/regression/research/agent/user/model/keys/test.py
git commit -F /tmp/tradingagents-lore-commit.txt
```

## Task 5: Add Research Principal, Permissions, And Tool Registry

**Files:**

- Create: `backend/app/services/research/agent/context.py`
- Create: `backend/app/services/research/agent/permissions.py`
- Create: `backend/app/services/research/agent/registry.py`
- Create: `backend/app/services/research/agent/tools/market/data.py`
- Create: `backend/app/services/research/agent/tools/analysis.py`
- Create: `backend/app/services/research/agent/tools/reports.py`
- Create: `backend/app/services/research/agent/tools/screening.py`
- Create: `backend/tests/regression/research/agent/permissions/test.py`
- Create: `backend/tests/regression/research/agent/tool/registry/test.py`

- [ ] **Step 1: Write failing permission tests**

Test that normal users can see research tools but not admin tools:

```python
principal = ResearchPrincipal.from_user({"id": "u1", "is_admin": False, "roles": []})
tools = ResearchToolRegistry.default().for_principal(principal)
names = {tool.name for tool in tools}
assert "single_stock_analysis" in names
assert "admin_config_write" not in names
```

- [ ] **Step 2: Implement `ResearchPrincipal` and permissions**

Create:

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class ResearchPrincipal:
    user_id: str
    role: str
    permissions: frozenset[str]
    session_id: str | None = None

    @classmethod
    def from_user(cls, user: dict, session_id: str | None = None) -> "ResearchPrincipal":
        roles = set(user.get("roles") or [])
        is_admin = bool(user.get("is_admin")) or "admin" in roles
        permissions = normal_user_permissions()
        if is_admin:
            permissions = permissions | admin_permissions()
        return cls(
            user_id=str(user["id"]),
            role="admin" if is_admin else "user",
            permissions=frozenset(permissions),
            session_id=session_id,
        )
```

- [ ] **Step 3: Implement tool registry**

Define `ResearchTool` with `name`, `description`, `permission`, `schema`, and
`run(context, payload)`. `for_principal` must filter by permission before any
prompt or tool-call code can see a tool.

- [ ] **Step 4: Wrap initial TradingAgents-CN tools**

Add initial wrappers for:

- `market_data_lookup`
- `screening_run`
- `single_stock_analysis`
- `batch_stock_analysis`
- `report_lookup`
- `report_write`

Each wrapper accepts `ToolExecutionContext`, validates `context.principal`, and
calls existing services rather than importing UI or route code. The
`market_data_lookup` wrapper should use existing TradingAgents-CN stock/data
services and return quote/history/fundamental snippets sized for Agent context;
it must not call Vibe loaders or unrestricted URL fetchers.

- [ ] **Step 5: Run registry tests**

```bash
cd backend
conda run -n trader pytest tests/regression/research/agent/permissions/test.py tests/regression/research/agent/tool/registry/test.py -q
```

Expected: all permission and registry tests pass.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/research/agent backend/tests/regression/research/agent/permissions/test.py backend/tests/regression/research/agent/tool/registry/test.py
git commit -F /tmp/tradingagents-lore-commit.txt
```

## Task 6: Add Persistent Research Sessions, Messages, Events, And Artifacts

**Files:**

- Create: `backend/app/services/research/agent/models.py`
- Create: `backend/app/services/research/agent/sessions.py`
- Create: `backend/app/services/research/agent/events.py`
- Create: `backend/app/services/research/agent/artifacts.py`
- Create: `backend/app/routers/research/agent.py`
- Create: `backend/tests/regression/research/agent/sessions/events/test.py`
- Modify: `backend/app/main/imports.py`
- Modify: `backend/app/main/application.py`

- [ ] **Step 1: Write failing session and event tests**

Test:

- user can create/list own sessions;
- user A cannot read user B session;
- events replay after a given event id;
- private artifact lookup enforces owner.

- [ ] **Step 2: Implement service models**

Use the existing storage abstraction used by report and analysis services.
Models should contain exact owner fields:

```python
session = {
    "session_id": session_id,
    "user_id": principal.user_id,
    "title": title,
    "status": "active",
    "created_at": now,
    "updated_at": now,
}
```

- [ ] **Step 3: Implement event replay**

`events.append(...)` persists each event and returns a monotonic event id.
`events.list_after(session_id, user_id, after_event_id)` returns only the
current user's events for that session.

- [ ] **Step 4: Implement router endpoints**

Add:

```text
POST /api/research-agent/sessions
GET  /api/research-agent/sessions
GET  /api/research-agent/sessions/{session_id}
POST /api/research-agent/sessions/{session_id}/messages
GET  /api/research-agent/sessions/{session_id}/messages
GET  /api/research-agent/sessions/{session_id}/events
```

SSE endpoint must check session ownership before streaming.

- [ ] **Step 5: Register research Agent router**

Import the router in `backend/app/main/imports.py`:

```python
from app.routers.research import agent as research_agent
```

Include it in `backend/app/main/application.py`:

```python
app.include_router(research_agent.router, prefix="/api/research-agent", tags=["research-agent"])
```

- [ ] **Step 6: Run session/event tests**

```bash
cd backend
conda run -n trader pytest tests/regression/research/agent/sessions/events/test.py -q
```

Expected: all session, ownership, replay, and route-registration tests pass.

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/research/agent/models.py backend/app/services/research/agent/sessions.py backend/app/services/research/agent/events.py backend/app/services/research/agent/artifacts.py backend/app/routers/research/agent.py backend/app/main/imports.py backend/app/main/application.py backend/tests/regression/research/agent/sessions/events/test.py
git commit -F /tmp/tradingagents-lore-commit.txt
```

## Task 7: Add Research Job Model For Agent, Alpha, And Matrix Work

**Files:**

- Create: `backend/app/services/research/agent/jobs.py`
- Modify: `backend/app/services/research/agent/events.py`
- Create: `backend/tests/regression/research/agent/jobs/test.py`

- [ ] **Step 1: Write failing job tests**

Test non-symbol jobs:

```python
job = await jobs.enqueue(
    principal=principal,
    task_type="correlation",
    resource_id="artifact-1",
    payload={"symbols": ["300750.SZ", "002594.SZ"]},
)
assert job["symbol"] is None
assert job["user_id"] == principal.user_id
```

Also test ownership for status, cancel, and event stream lookup.

- [ ] **Step 2: Implement typed job service**

Support:

- `enqueue(principal, task_type, resource_id, payload, symbol=None)`
- `get(job_id, user_id)`
- `cancel(job_id, user_id)`
- `mark_running(job_id)`
- `mark_completed(job_id, result)`
- `mark_failed(job_id, error)`

Persist events on each state change.

- [ ] **Step 3: Enforce quota and concurrency**

Use existing user quota/concurrency concepts where available:

- `daily_quota`;
- `concurrent_limit`;
- system-level queue caps.

If a user limit is not available in a helper, store the extension point in this
service and default to current system constants.

- [ ] **Step 4: Run job tests**

```bash
cd backend
conda run -n trader pytest tests/regression/research/agent/jobs/test.py -q
```

Expected: typed non-symbol jobs work and ownership checks pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/research/agent/jobs.py backend/app/services/research/agent/events.py backend/tests/regression/research/agent/jobs/test.py
git commit -F /tmp/tradingagents-lore-commit.txt
```

## Task 8: Port Safe Agent Loop Behavior

**Files:**

- Create: `backend/app/services/research/agent/loop.py`
- Modify: `backend/app/services/research/agent/registry.py`
- Create: `backend/tests/regression/research/agent/agent/loop/test.py`

- [ ] **Step 1: Write failing Agent loop tests**

Test:

- prompt only includes filtered tool names;
- model text chunks are appended to events;
- tool calls create tool events and persisted tool messages;
- finish reason `length` triggers one continuation;
- final content persists after refresh by reading messages from storage.

- [ ] **Step 2: Implement loop without Vibe prompt**

Build the system prompt from TradingAgents-CN facts and filtered tools:

```python
available_tools = registry.for_principal(principal)
prompt = build_research_prompt(principal=principal, tools=available_tools)
```

Do not include shell, file edit, live trading, or static Vibe swarm/tool claims.

- [ ] **Step 3: Implement streaming events**

Emit:

- `assistant_delta`
- `tool_started`
- `tool_completed`
- `tool_failed`
- `message_completed`
- `task_completed`
- `task_failed`
- `task_cancelled`

Every emitted event must be persisted through `research_events`.

- [ ] **Step 4: Run Agent loop tests**

```bash
cd backend
conda run -n trader pytest tests/regression/research/agent/agent/loop/test.py -q
```

Expected: loop tests pass and generated output can be reloaded from persisted
messages.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/research/agent/loop.py backend/app/services/research/agent/registry.py backend/tests/regression/research/agent/agent/loop/test.py
git commit -F /tmp/tradingagents-lore-commit.txt
```

## Task 9: Port Alpha Factor Core And Panel Loader

**Files:**

- Create: `backend/trader/factors/base.py`
- Create: `backend/trader/factors/registry.py`
- Create: `backend/trader/factors/factor/analysis/core.py`
- Create: `backend/trader/factors/bench/runner.py`
- Create: `backend/trader/factors/compare/runner.py`
- Create: `backend/trader/factors/panel/loader.py`
- Create directories: `backend/trader/factors/zoo/alpha101/`,
  `backend/trader/factors/zoo/gtja191/`, `backend/trader/factors/zoo/qlib158/`
- Create: `backend/tests/regression/alpha/zoo/factor/registry/test.py`
- Create: `backend/tests/regression/alpha/zoo/panel/loader/test.py`

- [ ] **Step 1: Write deterministic factor registry tests**

Test that registry loads known IDs:

```python
registry = FactorRegistry.discover()
assert "alpha101_001" in registry.ids()
assert registry.get("alpha101_001").metadata.required_columns
```

Use these canonical ID formats throughout the port:

- `alpha101_001` through `alpha101_101`;
- `gtja191_001` through `gtja191_191`;
- `qlib158_001` through `qlib158_158`.

- [ ] **Step 2: Write panel loader unit tests**

Use a deterministic fixture with two symbols and three trading dates. Test:

- required columns exist;
- missing symbols appear in `_meta.missing_symbols`;
- `amount` and `volume` units are recorded;
- `vwap` uses normalized units.

- [ ] **Step 3: Port base operators and metadata schema**

Move safe factor math from Vibe into `backend/trader/factors`. Replace imports
from `src.factors` with `trader.factors`.

- [ ] **Step 4: Implement TradingAgents-CN panel loader**

Read through TradingAgents-CN market/historical services or DB. Do not read
Vibe CSV paths and do not use `~/.vibe-trading/cache`.

- [ ] **Step 5: Run Alpha core tests**

```bash
cd backend
conda run -n trader pytest tests/regression/alpha/zoo/factor/registry/test.py tests/regression/alpha/zoo/panel/loader/test.py -q
```

Expected: factor registry and panel loader tests pass.

- [ ] **Step 6: Commit**

```bash
git add backend/trader/factors backend/tests/regression/alpha/zoo/factor/registry/test.py backend/tests/regression/alpha/zoo/panel/loader/test.py
git commit -F /tmp/tradingagents-lore-commit.txt
```

## Task 10: Add Alpha Zoo APIs And Private Jobs

**Files:**

- Create: `backend/app/services/alpha/zoo/schemas.py`
- Create: `backend/app/services/alpha/zoo/service.py`
- Create: `backend/app/services/alpha/zoo/jobs.py`
- Create: `backend/app/routers/alpha/zoo.py`
- Create: `backend/tests/regression/alpha/zoo/jobs/scope/test.py`
- Modify: `backend/app/main/imports.py`
- Modify: `backend/app/main/application.py`

- [ ] **Step 1: Write failing API/job ownership tests**

Test:

- factor list is public to authenticated users;
- user A can create own bench job;
- user A cannot read user B's bench job;
- user A cannot stream user B's bench events.

- [ ] **Step 2: Implement routes**

Add:

```text
GET  /api/alpha-zoo/list
GET  /api/alpha-zoo/{alpha_id}
POST /api/alpha-zoo/bench
GET  /api/alpha-zoo/jobs/{job_id}
GET  /api/alpha-zoo/jobs/{job_id}/events
POST /api/alpha-zoo/compare
```

Use `research_jobs` for bench/compare execution and `research_artifacts` for
results.

- [ ] **Step 3: Register Alpha router and tools**

Import the router in `backend/app/main/imports.py`:

```python
from app.routers.alpha import zoo as alpha_zoo
```

Include it in `backend/app/main/application.py`:

```python
app.include_router(alpha_zoo.router, prefix="/api/alpha-zoo", tags=["alpha-zoo"])
```

Add `alpha_list`, `alpha_detail`, `alpha_bench`, and `alpha_compare` to the
research tool registry with permissions:

```text
research.alpha.read
research.alpha.run
```

- [ ] **Step 4: Run Alpha API tests**

```bash
cd backend
conda run -n trader pytest tests/regression/alpha/zoo/jobs/scope/test.py -q
```

Expected: Alpha API ownership tests pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/alpha/zoo backend/app/routers/alpha/zoo.py backend/app/services/research/agent/tools/alpha.py backend/app/main/imports.py backend/app/main/application.py backend/tests/regression/alpha/zoo/jobs/scope/test.py
git commit -F /tmp/tradingagents-lore-commit.txt
```

## Task 11: Add Correlation Matrix APIs And Private Jobs

**Files:**

- Create: `backend/app/routers/research/matrix.py`
- Create: `backend/app/services/research/agent/tools/correlation.py`
- Create: `backend/tests/regression/research/matrix/jobs/scope/test.py`
- Modify: `backend/app/main/imports.py`
- Modify: `backend/app/main/application.py`

- [ ] **Step 1: Write failing correlation ownership tests**

Test:

- user A can create matrix job from explicit symbols;
- user A cannot read user B's matrix job;
- invalid or unowned `screening_result_id` returns `404`;
- matrix result persists as a private artifact.

- [ ] **Step 2: Implement matrix service and routes**

Add:

```text
POST /api/research-matrix/correlation
GET  /api/research-matrix/jobs/{job_id}
GET  /api/research-matrix/jobs/{job_id}/events
```

Use explicit symbols, favorites, sector, or persisted user-owned universe as
input. Reject `screening_result_id` until screening runs are persisted.

- [ ] **Step 3: Register matrix router and correlation tool**

Import the router in `backend/app/main/imports.py`:

```python
from app.routers.research import matrix as research_matrix
```

Include it in `backend/app/main/application.py`:

```python
app.include_router(research_matrix.router, prefix="/api/research-matrix", tags=["research-matrix"])
```

Add `correlation_matrix` to the research tool registry with permission:

```text
research.correlation.run
```

- [ ] **Step 4: Run matrix tests**

```bash
cd backend
conda run -n trader pytest tests/regression/research/matrix/jobs/scope/test.py -q
```

Expected: correlation job ownership and artifact tests pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/research/matrix.py backend/app/services/research/agent/tools/correlation.py backend/app/main/imports.py backend/app/main/application.py backend/tests/regression/research/matrix/jobs/scope/test.py
git commit -F /tmp/tradingagents-lore-commit.txt
```

## Task 12: Add Next.js Agent, Alpha Zoo, And Correlation Pages

**Files:**

- Create: `frontend/app/agent/page.tsx`
- Create: `frontend/app/agent/loading.tsx`
- Create: `frontend/app/alpha-zoo/page.tsx`
- Create: `frontend/app/alpha-zoo/loading.tsx`
- Create: `frontend/app/correlation/page.tsx`
- Create: `frontend/app/correlation/loading.tsx`
- Create: `frontend/features/research-agent/research-agent-page.tsx`
- Create: `frontend/features/research-agent/session-sidebar.tsx`
- Create: `frontend/features/research-agent/message-timeline.tsx`
- Create: `frontend/features/research-agent/tool-timeline.tsx`
- Create: `frontend/features/research-agent/artifact-drawer.tsx`
- Create: `frontend/features/alpha-zoo/alpha-zoo-page.tsx`
- Create: `frontend/features/alpha-zoo/alpha-factor-table.tsx`
- Create: `frontend/features/alpha-zoo/alpha-bench-runner.tsx`
- Create: `frontend/features/research-matrix/correlation-page.tsx`
- Create: `frontend/features/research-matrix/correlation-heatmap.tsx`
- Create: `frontend/libs/api/research-agent.ts`
- Create: `frontend/libs/api/alpha-zoo.ts`
- Create: `frontend/libs/api/research-matrix.ts`
- Modify: `frontend/libs/routes/route-config.ts`
- Create: `frontend/tests/components/research-agent-page.test.tsx`
- Create: `frontend/tests/components/alpha-zoo-page.test.tsx`
- Create: `frontend/tests/components/correlation-page.test.tsx`
- Modify: `frontend/tests/routes/page-loading.test.ts`
- Modify: `frontend/tests/routes/route-config.test.ts`

- [ ] **Step 1: Write failing component tests**

Test:

- `/agent` renders session list, message timeline, tool timeline, artifact
  drawer, cancel, retry, and final report areas;
- `/alpha-zoo` renders filters, factor table, detail, and bench runner;
- `/correlation` renders universe selector, date/window controls, method
  selector, heatmap, and candidate lists.

- [ ] **Step 2: Implement API clients**

Use existing `frontend/libs/api/request.ts` conventions. Each API client should
return typed results and preserve API errors for private resource messages.

- [ ] **Step 3: Implement pages, loading files, and components**

Use existing page/component style. Keep UI dense and workspace-oriented. Do not
build marketing hero sections.

Each new route must include a sibling `loading.tsx` using the existing loading
pattern:

```tsx
import { PageLoading } from "@/components/feedback/page-loading"

export default function Loading() {
  return <PageLoading />
}
```

- [ ] **Step 4: Add navigation and route config entries**

Modify the existing route/nav configuration so `/agent`, `/alpha-zoo`, and
`/correlation` are reachable. Update `frontend/libs/routes/route-config.ts` and
adjust `frontend/tests/routes/route-config.test.ts` expectations so these
routes are part of the tested route/menu set.

- [ ] **Step 5: Run frontend component tests**

```bash
cd frontend
pnpm test tests/components/research-agent-page.test.tsx tests/components/alpha-zoo-page.test.tsx tests/components/correlation-page.test.tsx
pnpm test tests/routes/page-loading.test.ts tests/routes/route-config.test.ts
```

Expected: all new component tests pass, page-loading tests find sibling
`loading.tsx` files, and route-config tests include the three new routes.

- [ ] **Step 6: Commit**

```bash
git add frontend/app/agent frontend/app/alpha-zoo frontend/app/correlation frontend/features/research-agent frontend/features/alpha-zoo frontend/features/research-matrix frontend/libs/api/research-agent.ts frontend/libs/api/alpha-zoo.ts frontend/libs/api/research-matrix.ts frontend/libs/routes/route-config.ts frontend/tests/components/research-agent-page.test.tsx frontend/tests/components/alpha-zoo-page.test.tsx frontend/tests/components/correlation-page.test.tsx frontend/tests/routes/page-loading.test.ts frontend/tests/routes/route-config.test.ts
git commit -F /tmp/tradingagents-lore-commit.txt
```

## Task 13: Add End-To-End Research Workflow And Final Report Synthesis

**Files:**

- Modify: `backend/app/services/research/agent/loop.py`
- Modify: `backend/app/services/research/agent/tools/reports.py`
- Modify: `backend/app/routers/research/agent.py`
- Create: `frontend/tests/e2e/research-workflow.spec.ts`
- Create: `backend/tests/regression/research/agent/report/synthesis/test.py`

- [ ] **Step 1: Write report synthesis tests**

Test that final report output includes:

- sector summary;
- universe construction method;
- screening filters;
- correlation findings;
- Alpha/factor findings;
- linked single-stock reports;
- recommended stocks when evidence exists;
- risk factors;
- data limitations;
- linked artifacts and task ids.

- [ ] **Step 2: Implement structured report writer**

`report_write` should persist structured sections and link artifact ids. If
evidence is missing, write a limitation section instead of a recommendation.

- [ ] **Step 3: Write E2E workflow test**

Use Playwright route mocks for these exact endpoints:

```typescript
await page.route("**/api/research-agent/sessions", route => {
  if (route.request().method() === "GET") {
    return route.fulfill({ json: { success: true, data: [] } });
  }
  return route.fulfill({
    json: { success: true, data: { session_id: "session-a", title: "储能板块分析" } },
  });
});

await page.route("**/api/research-agent/sessions/session-a/messages", route => {
  return route.fulfill({
    json: { success: true, data: { task_id: "research-task-a" } },
  });
});

await page.route("**/api/research-agent/sessions/session-a/events", route => {
  return route.fulfill({
    body:
      "event: assistant_delta\n" +
      "data: {\"content\":\"储能板块分析进行中\"}\n\n" +
      "event: tool_completed\n" +
      "data: {\"tool_name\":\"alpha_bench\",\"artifact_id\":\"artifact-alpha-a\"}\n\n" +
      "event: message_completed\n" +
      "data: {\"content\":\"推荐个股：300750.SZ，理由见关联报告。\"}\n\n",
    headers: { "Content-Type": "text/event-stream" },
  });
});
```

Verify:

- user opens `/agent`;
- sends storage-sector prompt;
- sees streamed Markdown;
- sees tool timeline;
- sees final report card;
- refresh preserves final output.

- [ ] **Step 4: Run synthesis and E2E tests**

```bash
cd backend
conda run -n trader pytest tests/regression/research/agent/report/synthesis/test.py -q

cd ../frontend
pnpm test:e2e tests/e2e/research-workflow.spec.ts
```

Expected: backend synthesis and frontend workflow tests pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/research/agent/loop.py backend/app/services/research/agent/tools/reports.py backend/app/routers/research/agent.py backend/tests/regression/research/agent/report/synthesis/test.py frontend/tests/e2e/research-workflow.spec.ts
git commit -F /tmp/tradingagents-lore-commit.txt
```

## Final Verification

Run backend verification:

```bash
cd backend
conda run -n trader pytest
conda run -n trader ruff check .
conda run -n trader pyright .
```

Expected:

- pytest exits `0`;
- ruff exits `0`;
- pyright exits `0`.

Run frontend verification:

```bash
cd frontend
pnpm test
pnpm type-check
pnpm build
```

Expected:

- Vitest exits `0`;
- TypeScript exits `0`;
- Next build exits `0`.

Manual verification:

- Start backend on a port other than `8000`.
- Start frontend.
- Log in as user A and user B.
- Confirm user A cannot access user B reports, tasks, Agent sessions, Alpha
  jobs, matrix jobs, artifacts, or SSE streams.
- Run "分析 A 股储能板块，给出推荐个股" from `/agent`.
- Refresh after completion and verify the final Markdown, tool timeline, and
  artifact links remain complete.

## Risks And Mitigations

| Risk | Mitigation |
| --- | --- |
| Existing report/task ownership leaks | Phase 0 tests and fixes before new UI |
| Vibe prompt exposes unavailable tools | Generate prompt from filtered registry only |
| Alpha result math is wrong because of A-share units | Panel loader records source and normalized units, with deterministic tests |
| Research jobs overload server | Typed queue, quotas, concurrency, cancellation, and job retention |
| MiniMax token-plan mismatch | Verify current client first, port Vibe adapter only if tool-call or finish handling fails |
| Browser refresh truncates output | Persist messages, events, and artifacts before streaming completion |

## Execution Handoff

Recommended execution mode:

- Use subagent-driven execution for independent lanes after Task 3:
  - backend security lane;
  - research session/event lane;
  - Alpha factor lane;
  - frontend workspace lane;
  - verifier lane.
- Keep Tasks 1 to 3 sequential because they establish security gates.
- Keep final workflow verification in one owner context so cross-feature
  behavior is checked end to end.

Do not merge or release until the Final Verification section passes.

## Review Fix Log

Updated on 2026-06-08 after plan review:

- Added admin gating coverage for compatibility LLM mutation routes in
  `backend/app/routers/config/legacy.py` and
  `backend/app/routers/config/catalog.py`.
- Changed backend regression test paths to directory-local `test.py` files so
  the repo's `python_files = ["test.py"]` setting collects them in the full
  pytest suite.
- Replaced vague backend router registration wording with concrete
  `backend/app/main/imports.py` imports and `backend/app/main/application.py`
  `include_router` steps.
- Added required frontend `loading.tsx` files and route-config updates for the
  new `/agent`, `/alpha-zoo`, and `/correlation` pages.
- Added a dedicated private user model key task with storage, owner-scoped API,
  redaction, audit, router registration, and tests.
- Fixed the report-owner persistence example so it resolves `task_doc` before
  reading owner fields.
- Added the missing initial `market_data_lookup` tool wrapper.
- Replaced one-line commit examples with the Lore commit protocol and
  `git commit -F /tmp/tradingagents-lore-commit.txt`.
