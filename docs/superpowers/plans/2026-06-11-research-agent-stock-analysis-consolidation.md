# 研究 Agent 合并单股/批量分析实施计划

> **给执行 agent：** 必须使用 `superpowers:subagent-driven-development`（推荐）或 `superpowers:executing-plans` 按任务执行。所有步骤使用复选框（`- [ ]`）跟踪。

**目标：** 让研究 Agent 成为单股分析和批量分析的统一入口，同时复用现有分析任务、队列、状态和报告系统。

**架构：** 股票分析的执行仍留在现有 analysis service 和 queue 中。研究 Agent 只增加工具适配层：提交任务、查询状态、读取报告，并以当前用户身份访问。前端先在 `/agent` 增加单股/批量快捷入口，旧分析页面继续保留。

**技术栈：** FastAPI、现有 TradingAgents-CN document store、现有 queue service、Research Agent tool registry、pytest、Ruff、Next.js、React、Vitest、TypeScript。

---

## 范围

本计划实现：

`docs/superpowers/specs/2026-06-11-research-agent-stock-analysis-consolidation.md`

计划不删除旧分析路由，不重写股票分析引擎，只把研究 Agent 接到现有能力上。

## 文件地图

### 后端主要修改文件

- `backend/app/services/research/agent/tools/analysis.py`
  - 把占位工具改成真实提交、状态读取、报告读取适配器。
- `backend/app/services/research/agent/registry.py`
  - 如果新增独立工具，在 registry 中注册。
- `backend/app/services/research/agent/permissions.py`
  - 如果拆出新工具权限，在这里补权限。
- `backend/app/services/research/agent/loop.py`
  - 不预期大改；只确认 tool event 继续携带 `attempt_id`、`task_id`、`batch_id`。
- `backend/app/services/research/agent/artifacts.py`
  - 如需要，增加保存 task/batch/report 引用的 helper。
- `backend/app/services/research/agent/tools/reports.py`
  - 如果报告读取逻辑不适合放在 `analysis.py`，复用或扩展这里。
- `backend/app/services/analysis/simple/service.py`
  - 只有在缺少 owner-scoped 查询方法时才修改。
- `backend/app/routers/analysis/result.py`
  - 只有在报告读取需要复用 owner-scoped helper 时才修改。

### 后端测试文件

- `backend/tests/regression/research/agent/tool/calls/test.py`
  - 增加股票分析工具提交、状态、报告读取测试。
- `backend/tests/regression/research/agent/agent/loop/test.py`
  - 保持工具事件 attempt 归属和系统提示词约束回归。
- `backend/tests/regression/analysis/user/isolation/test.py`
  - 如果暴露新读取路径时发现隔离覆盖不足，在这里补测试。

### 前端主要修改文件

- `frontend/features/research-agent/research-agent-page.tsx`
  - 增加单股/批量快捷入口。
  - 支持从 `/agent?prompt=...` 初始化输入框。
- `frontend/libs/api/research-agent.ts`
  - 预计不需要大改；如快捷入口需要类型，可补辅助类型。
- `frontend/features/dashboard/dashboard-page.tsx`
  - 后续增加 Agent 入口。
- `frontend/features/stocks/stock-detail-page.tsx`
  - 后续增加 Agent 入口。
- `frontend/features/favorites/favorites-page.tsx`
  - 后续增加 Agent 入口。
- `frontend/features/screening/screening-page.tsx`
  - 后续增加 Agent 入口。

### 前端测试文件

- `frontend/tests/components/research-agent-page.test.tsx`
  - 增加快捷入口和 `prompt` 查询参数初始化测试。
- 现有 route 测试应继续通过，因为旧路由保留。

## 任务 1：用失败测试锁定当前占位问题

**文件：**

- 修改：`backend/tests/regression/research/agent/tool/calls/test.py`
- 失败后修改：`backend/app/services/research/agent/tools/analysis.py`

- [ ] **步骤 1：添加单股分析提交失败测试**

在 `tool/calls/test.py` 中添加测试。测试通过 registry 获取 `single_stock_analysis` 工具，调用时传入当前用户上下文。

期望行为：

```python
result = await tool.run(
    ToolExecutionContext(
        principal=ResearchPrincipal.from_user(USER_A, session_id="session-a"),
        session_id="session-a",
        request_id="attempt-a",
    ),
    {"symbol": "600519", "market_type": "A股", "research_depth": "标准"},
)

assert result["tool"] == "stock_analysis"
assert result["mode"] == "single"
assert result["status"] == "submitted"
assert result["symbol"] == "600519"
assert result["task_id"] == "task-600519"
assert result["links"]["task"] == "/tasks?task_id=task-600519"
```

测试中 monkeypatch 现有分析提交依赖，让它返回：

```python
{"task_id": "task-600519", "symbol": "600519", "status": "pending"}
```

- [ ] **步骤 2：运行单股测试确认失败态**

运行：

```bash
PYTHONPATH=backend python -m pytest backend/tests/regression/research/agent/tool/calls/test.py::test_single_stock_analysis_tool_submits_existing_analysis_task -q
```

期望：失败。当前工具只返回 `accepted=True` 和原 payload。

- [ ] **步骤 3：添加批量分析提交失败测试**

期望行为：

```python
result = await tool.run(
    context,
    {"symbols": ["AAPL", "MSFT"], "market_type": "美股"},
)

assert result["tool"] == "stock_analysis"
assert result["mode"] == "batch"
assert result["status"] == "submitted"
assert result["batch_id"] == "batch-1"
assert result["total_tasks"] == 2
assert result["tasks"] == [
    {"symbol": "AAPL", "task_id": "task-aapl"},
    {"symbol": "MSFT", "task_id": "task-msft"},
]
assert result["links"]["batch"] == "/tasks?batch_id=batch-1"
```

- [ ] **步骤 4：运行批量测试确认失败态**

运行：

```bash
PYTHONPATH=backend python -m pytest backend/tests/regression/research/agent/tool/calls/test.py::test_batch_stock_analysis_tool_submits_existing_analysis_batch -q
```

期望：失败。当前批量工具还是占位。

## 任务 2：实现单股/批量提交适配器

**文件：**

- 修改：`backend/app/services/research/agent/tools/analysis.py`
- 测试：`backend/tests/regression/research/agent/tool/calls/test.py`

- [ ] **步骤 1：增加参数构造 helper**

在 `analysis.py` 中实现：

```python
def _analysis_parameters_from_payload(payload: dict[str, Any]) -> AnalysisParameters:
    return AnalysisParameters(
        market_type=str(payload.get("market_type") or "A股"),
        analysis_date=payload.get("analysis_date"),
        research_depth=str(payload.get("research_depth") or "标准"),
        selected_analysts=list(
            payload.get("selected_analysts")
            or ["market", "fundamentals", "news", "social"]
        ),
        include_sentiment=bool(payload.get("include_sentiment", True)),
        include_risk=bool(payload.get("include_risk", True)),
        language=str(payload.get("language") or "zh-CN"),
        quick_analysis_model=payload.get("quick_analysis_model") or "qwen-turbo",
        deep_analysis_model=payload.get("deep_analysis_model") or "qwen-max",
    )
```

如果 `analysis_date` 字符串不能直接被 `AnalysisParameters` 接受，就按旧分析 route 已有逻辑做日期转换。

- [ ] **步骤 2：实现单股提交**

优先复用现有 `/api/analysis/single` 等价的 service 调用路径：

- `get_simple_analysis_service()`
- `get_queue_service()`
- `_analysis_request_queue_params(...)` 等已有 helper

返回结构必须稳定：

```python
{
    "tool": "stock_analysis",
    "mode": "single",
    "status": "submitted",
    "symbol": symbol,
    "task_id": task_id,
    "links": {
        "task": f"/tasks?task_id={task_id}",
        "report": None,
    },
    "message": "单股分析任务已提交，结果生成后可继续让 Agent 总结。",
}
```

- [ ] **步骤 3：实现批量提交**

复用现有 batch 逻辑，继续保持最多 10 只股票限制。

如果现有 batch 返回没有 task mapping，则通过 `batch_id + user_id` 查询刚创建的 `analysis_tasks`。

返回结构必须稳定：

```python
{
    "tool": "stock_analysis",
    "mode": "batch",
    "status": "submitted",
    "batch_id": batch_id,
    "total_tasks": len(tasks),
    "tasks": tasks,
    "links": {
        "batch": f"/tasks?batch_id={batch_id}",
    },
    "message": "批量分析任务已提交。",
}
```

- [ ] **步骤 4：保留兼容工具名**

保留：

- `single_stock_analysis`
- `batch_stock_analysis`

但它们内部调用同一套 helper，不复制逻辑。

- [ ] **步骤 5：运行提交测试确认通过态**

运行：

```bash
PYTHONPATH=backend python -m pytest backend/tests/regression/research/agent/tool/calls/test.py::test_single_stock_analysis_tool_submits_existing_analysis_task backend/tests/regression/research/agent/tool/calls/test.py::test_batch_stock_analysis_tool_submits_existing_analysis_batch -q
```

期望：通过。

## 任务 3：增加状态读取和报告读取工具

**文件：**

- 修改：`backend/app/services/research/agent/tools/analysis.py`
- 修改：`backend/app/services/research/agent/registry.py`
- 测试：`backend/tests/regression/research/agent/tool/calls/test.py`

- [ ] **步骤 1：添加状态工具失败测试**

添加这些测试：

- `stock_analysis_status` 使用 `task_id` 查询；
- `stock_analysis_status` 使用 `batch_id` 查询；
- 查询其他用户的 `task_id` 返回安全的 not-found 结果。

期望 task 状态结果：

```python
{
    "tool": "stock_analysis_status",
    "status": "completed",
    "task_id": "task-1",
    "symbol": "600519",
    "progress": 100,
    "links": {
        "task": "/tasks?task_id=task-1",
        "report": "/reports/view/analysis-1",
    },
}
```

- [ ] **步骤 2：运行状态测试确认失败态**

运行：

```bash
PYTHONPATH=backend python -m pytest backend/tests/regression/research/agent/tool/calls/test.py -q -k stock_analysis_status
```

期望：失败，因为工具还不存在。

- [ ] **步骤 3：实现 `stock_analysis_status`**

实现要求：

- 只使用 `context.principal.user_id`。
- 不接受 payload 里的 `user_id`。
- pending 返回 pending 和说明。
- failed 返回错误原因。
- completed 返回任务链接和报告链接。

pending 输出示例：

```python
{
    "tool": "stock_analysis_status",
    "status": "pending",
    "task_id": task_id,
    "message": "分析任务仍在排队或执行中，尚未生成最终报告。",
}
```

- [ ] **步骤 4：添加报告读取失败测试**

测试：

- 通过 `task_id` 读取已完成报告；
- 通过 `analysis_id` 读取报告；
- 读取其他用户报告返回安全 not-found。

期望输出：

```python
{
    "tool": "stock_analysis_report",
    "status": "completed",
    "task_id": "task-1",
    "analysis_id": "analysis-1",
    "summary": "报告摘要",
    "recommendation": "持有",
    "risk_level": "中",
    "links": {
        "report": "/reports/view/analysis-1",
    },
}
```

- [ ] **步骤 5：实现 `stock_analysis_report`**

优先复用已有报告恢复 helper。

如果没有 owner-scoped helper，先补 helper，再暴露给 Agent。

- [ ] **步骤 6：运行状态/报告测试确认通过态**

运行：

```bash
PYTHONPATH=backend python -m pytest backend/tests/regression/research/agent/tool/calls/test.py -q -k "stock_analysis_status or stock_analysis_report"
```

期望：通过。

## 任务 4：为 Agent 写入股票分析 Artifact

**文件：**

- 修改：`backend/app/services/research/agent/tools/analysis.py`
- 可选修改：`backend/app/services/research/agent/artifacts.py`
- 测试：`backend/tests/regression/research/agent/tool/calls/test.py`

- [ ] **步骤 1：添加 artifact 失败测试**

单股提交后应存在 `stock_analysis_task` artifact：

```python
{
    "artifact_type": "stock_analysis_task",
    "payload": {
        "task_id": "task-600519",
        "symbol": "600519",
        "mode": "single",
    },
}
```

批量提交后应存在 `stock_analysis_batch` artifact：

```python
{
    "artifact_type": "stock_analysis_batch",
    "payload": {
        "batch_id": "batch-1",
        "symbols": ["AAPL", "MSFT"],
        "task_ids": ["task-aapl", "task-msft"],
    },
}
```

- [ ] **步骤 2：运行 artifact 测试确认失败态**

运行：

```bash
PYTHONPATH=backend python -m pytest backend/tests/regression/research/agent/tool/calls/test.py -q -k stock_analysis_artifact
```

期望：失败，因为还没有 artifact 写入。

- [ ] **步骤 3：在工具 handler 中写 artifact**

使用：

```python
ResearchArtifactService().create_artifact(...)
```

要求：

- 使用当前 `session_id`；
- 使用当前 `user_id`；
- metadata 中保存 `attempt_id`；
- payload 中保存 `task_id` 或 `batch_id`。

- [ ] **步骤 4：工具结果返回 artifact_id**

把 `artifact_id` 放入工具返回值，让 Agent loop 可以把 artifact 关联到最终回答。

- [ ] **步骤 5：运行 artifact 测试确认通过态**

运行：

```bash
PYTHONPATH=backend python -m pytest backend/tests/regression/research/agent/tool/calls/test.py -q -k stock_analysis_artifact
```

期望：通过。

## 任务 5：更新 Agent 提示词 和工具描述

**文件：**

- 修改：`backend/app/services/research/agent/loop.py`
- 修改：`backend/app/services/research/agent/tools/analysis.py`
- 测试：`backend/tests/regression/research/agent/agent/loop/test.py`

- [ ] **步骤 1：添加 提示词 回归测试**

测试 `build_research_提示词(...)` 包含这些要求：

- 单股/批量股票分析使用 `stock_analysis`；
- 没有 task/report ID 时先提交任务；
- 后续问题使用 status/report 工具检查真实状态；
- pending 任务不能编造成已完成结论。

- [ ] **步骤 2：运行 提示词 测试确认失败态**

运行：

```bash
PYTHONPATH=backend python -m pytest backend/tests/regression/research/agent/agent/loop/test.py -q -k stock_analysis_提示词
```

期望：失败，直到系统提示词约束更新。

- [ ] **步骤 3：更新工具描述**

建议描述：

```text
stock_analysis: 提交现有单股或批量股票分析任务。
stock_analysis_status: 查询当前用户自己的股票分析任务或批次状态。
stock_analysis_report: 读取当前用户自己的已完成股票分析报告，再进行总结。
```

- [ ] **步骤 4：更新 Agent 系统提示词约束**

增加规则：

- 用户要求分析股票时，优先提交真实分析任务。
- 用户问刚才结果时，先查 status。
- 只有报告完成后才能总结。
- pending/failed 必须明确说明，不得编造。

- [ ] **步骤 5：运行 loop 测试确认通过态**

运行：

```bash
PYTHONPATH=backend python -m pytest backend/tests/regression/research/agent/agent/loop/test.py -q
```

期望：通过。

## 任务 6：在 `/agent` 增加单股/批量快捷入口

**文件：**

- 修改：`frontend/features/research-agent/research-agent-page.tsx`
- 测试：`frontend/tests/components/research-agent-page.test.tsx`

- [ ] **步骤 1：添加快捷入口失败测试**

测试：

- 页面出现 `单股分析` 快捷入口；
- 点击后 composer 被填入单股分析 提示词；
- 页面出现 `批量分析` 快捷入口；
- 点击后 composer 被填入批量分析 提示词；
- 不自动发送。

单股 提示词 示例：

```text
请对 600519 做单股分析，市场为 A股，研究深度为 标准。
```

批量 提示词 示例：

```text
请批量分析 600519, 000001, 300750，市场为 A股，研究深度为 标准。
```

- [ ] **步骤 2：运行前端测试确认失败态**

运行：

```bash
pnpm --pm-on-fail=ignore --dir frontend test tests/components/research-agent-page.test.tsx -- --pool=forks -t "stock analysis quick actions"
```

期望：失败，因为快捷入口还不存在。

- [ ] **步骤 3：实现快捷入口**

在 composer 附近或现有快捷操作区增加两个轻量按钮：

- `单股分析`
- `批量分析`

行为：

- 设置输入框内容；
- 留在 `/agent`；
- 不自动提交。

- [ ] **步骤 4：运行前端测试确认通过态**

运行：

```bash
pnpm --pm-on-fail=ignore --dir frontend test tests/components/research-agent-page.test.tsx -- --pool=forks -t "stock analysis quick actions"
```

期望：通过。

## 任务 7：支持 `/agent?prompt=...`

**文件：**

- 修改：`frontend/features/research-agent/research-agent-page.tsx`
- 测试：`frontend/tests/components/research-agent-page.test.tsx`

- [ ] **步骤 1：添加 `prompt` 查询参数失败测试**

测试打开：

```text
/agent?prompt=请对600519做单股分析
```

期望：

- composer 中出现 decoded 提示词；
- 不自动发送；
- 页面保持可编辑。

- [ ] **步骤 2：运行测试确认失败态**

运行：

```bash
pnpm --pm-on-fail=ignore --dir frontend test tests/components/research-agent-page.test.tsx -- --pool=forks -t "hydrates composer from prompt query"
```

期望：失败。

- [ ] **步骤 3：实现 `prompt` 查询参数初始化**

使用 Next 的 search params 读取 `prompt`。

只在首次加载时填充输入框，避免覆盖用户正在编辑的文本。

- [ ] **步骤 4：运行测试确认通过态**

运行：

```bash
pnpm --pm-on-fail=ignore --dir frontend test tests/components/research-agent-page.test.tsx -- --pool=forks -t "hydrates composer from prompt query"
```

期望：通过。

## 任务 8：给旧页面增加 Agent 辅助入口

**文件：**

- 修改：`frontend/features/dashboard/dashboard-page.tsx`
- 修改：`frontend/features/stocks/stock-detail-page.tsx`
- 修改：`frontend/features/favorites/favorites-page.tsx`
- 修改：`frontend/features/screening/screening-page.tsx`
- 测试：对应组件测试；如果没有现成覆盖，则补最小测试。

- [ ] **步骤 1：添加 Agent 链接测试**

期望链接格式：

```text
/agent?prompt=<编码后的单股分析提示词>
/agent?prompt=<编码后的批量分析提示词>
```

- [ ] **步骤 2：运行测试确认失败态**

运行对应 frontend component tests。

- [ ] **步骤 3：增加辅助链接**

添加文案：

```text
用研究 Agent 分析
```

注意：

- 第一版不删除旧 `分析` 按钮。
- 第一版不改变旧提交行为。

- [ ] **步骤 4：运行测试确认通过态**

运行：

```bash
pnpm --pm-on-fail=ignore --dir frontend test tests/components/research-agent-page.test.tsx -- --pool=forks
pnpm --pm-on-fail=ignore --dir frontend type-check
```

期望：通过。

## 任务 9：验证

**文件：**

- 不预期修改生产文件。若验证失败，回到对应任务修复。

- [ ] **步骤 1：运行后端目标测试**

运行：

```bash
PYTHONPATH=backend python -m pytest backend/tests/regression/research/agent/tool/calls/test.py backend/tests/regression/research/agent/agent/loop/test.py backend/tests/regression/analysis/user/isolation/test.py -q
```

期望：通过。

- [ ] **步骤 2：运行后端 Ruff**

运行：

```bash
python -m ruff check backend/app/services/research/agent backend/tests/regression/research/agent backend/tests/regression/analysis/user/isolation/test.py
```

期望：

```text
All checks passed!
```

- [ ] **步骤 3：运行前端目标测试**

运行：

```bash
pnpm --pm-on-fail=ignore --dir frontend test tests/components/research-agent-page.test.tsx -- --pool=forks
```

期望：通过。

- [ ] **步骤 4：运行前端类型检查和 lint**

运行：

```bash
pnpm --pm-on-fail=ignore --dir frontend type-check
pnpm --pm-on-fail=ignore --dir frontend lint
```

期望：通过。

- [ ] **步骤 5：本地 smoke**

启动或重启服务：

```bash
setsid zsh -lc 'cd /home/amaozhao/workspace/TradingAgents-CN/backend && exec conda run --no-capture-output -n trader python -m uvicorn app.main:app --host 0.0.0.0 --port 8000' > .omx/logs/backend-dev.log 2>&1 < /dev/null &
setsid zsh -lc 'cd /home/amaozhao/workspace/TradingAgents-CN/frontend && exec pnpm --pm-on-fail=ignore dev --hostname 127.0.0.1 --port 3000' > .omx/logs/frontend-dev.log 2>&1 < /dev/null &
```

检查：

```bash
curl -sS -w '\n%{http_code}\n' http://127.0.0.1:8000/api/health
curl -sS -w '\n%{http_code}\n' http://127.0.0.1:3000/api/health
curl -sS -I http://127.0.0.1:3000/agent | head
```

期望：

- 两个 health endpoint 返回 `200`；
- `/agent` 返回 `HTTP/1.1 200 OK`。

## 提交策略

建议分 4 个 commit：

1. `让研究 Agent 提交真实股票分析任务`
2. `让研究 Agent 读取股票分析状态和报告`
3. `在研究 Agent 页面提供股票分析快捷入口`
4. `把旧分析页面引导到研究 Agent`

每个 commit 必须遵守 `AGENTS.md` 中的 Lore commit protocol。

## 评审检查清单

- 是否保留了旧分析执行和报告存储？
- Agent 是否不会把 pending 任务说成完成？
- task/report 读取是否严格按当前用户过滤？
- 旧页面是否仍可用？
- 批量分析是否仍然异步？
- 工具输出是否包含前端可用的 task/batch/report 链接？
