# Async DB Runtime Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` for parallel task execution or `superpowers:executing-plans` for inline execution. Steps use checkbox (`- [ ]`) syntax for tracking. Do not modify source code until Phase 0 tests and review gates are satisfied.

**Goal:** 将 Web/Worker 运行时中的 PostgreSQL 同步封装调用逐步改为异步调用，减少重复连接池、阻塞等待和连接耗尽风险，同时保留 CLI、脚本和 legacy 同步调用链的兼容性。

**Architecture:** 不做全局一刀切替换。先治理 FastAPI、Worker、分析任务、模型配置等 async 运行时路径；再为 trader flow 和配置桥接增加 async companion API；最后把 `get_postgres_db_sync()` 收口为 CLI/脚本专用兼容层，并增加运行时防误用保护。

**Tech Stack:** Python、FastAPI、asyncio、SQLAlchemy AsyncEngine、APScheduler、pytest、Ruff、Pyright、PostgreSQL、conda env `trader`。

---

## 1. 结论

可以把大量同步 DB 调用改为异步调用，但不能直接把所有 `get_postgres_db_sync()` 全局替换成 `get_postgres_db()`。

必须保留三类边界：

- Web/Worker async 运行时：必须迁移到异步 DB。
- trader flow、数据源 provider、配置桥接：增加 async companion API，逐步迁移调用方。
- CLI、一次性脚本、legacy 同步入口：允许继续使用同步 facade，但要被隔离和限制连接池影响。

本改造不改变业务能力、API 成功响应、报告格式、用户权限、任务状态字段和数据源策略。目标是运行时稳定性和架构边界收敛。

## 2. 现状证据

### 2.1 同步封装的阻塞点

文件：

- `backend/app/db/store/sync.py`
- `backend/app/db/store/helpers.py`

证据：

- `SyncPostgresCollection.find_one()`、`insert_one()`、`update_one()`、`bulk_write()` 等方法都调用 `_run_blocking(...)`。
- `_run_blocking()` 使用 `asyncio.run_coroutine_threadsafe(coro, loop).result()` 阻塞等待结果。
- `_get_sync_loop()` 会创建独立后台线程和独立 event loop：`postgres-document-sync-loop`。

影响：

- async request/worker 中调用同步 facade 时，会阻塞当前调用链。
- 同步 facade 使用独立 event loop，可能触发另一套 PostgreSQL engine/session pool。
- `.result()` 没有显式 timeout，调用方取消和请求超时不能自然传播到底层 DB 操作。

### 2.2 连接池放大点

文件：

- `backend/app/core/session.py`
- `backend/app/core/config.py`

证据：

- `backend/app/core/session.py` 以 `asyncio.AbstractEventLoop` 作为 `_session_states` key。
- `init_postgres()` 为当前 event loop 创建 `create_async_engine(...)`。
- 默认配置为 `POSTGRES_POOL_SIZE=10`、`POSTGRES_MAX_OVERFLOW=20`。

推导：

```text
FastAPI 主 loop      -> 最多 30 连接
FastAPI sync facade  -> 最多 30 连接
Worker 主 loop       -> 最多 30 连接
Worker sync facade   -> 最多 30 连接
调度任务/其他进程     -> 继续增加
```

本地 PostgreSQL `max_connections=100` 时，多个进程和多个 event loop 很容易连接耗尽。

### 2.3 调度任务并发压力

文件：

- `backend/app/main/application.py`
- `backend/app/core/config.py`

证据：

- `AsyncIOScheduler(job_defaults={"coalesce": True, "max_instances": 1})` 只限制同一个 job 的实例数量，不限制不同 job 之间的全局并发。
- Tushare、AKShare、BaoStock、quotes ingestion、news sync 都会注册定时任务。
- Tushare/AKShare/BaoStock 多个同步开关默认启用。

影响：

- 即使所有 DB 调用改为 async，如果 scheduler 仍允许多个重型同步任务同时跑，连接池和外部数据源仍可能被压满。
- 本计划必须同时包含连接池配置和全局调度并发控制，否则只改 DB 调用不完整。

## 3. 适用 Standards

| Standard | 本计划约束 |
| --- | --- |
| `standards/database.md` | async 后端路径必须使用 `AsyncSession` / async document store；不得把阻塞 DB 调用混入 async request；事务归属不扩散。 |
| `standards/performance.md` | async 代码保持非阻塞；长循环要有有界并发；不靠盲目并发掩盖连接池问题。 |
| `standards/modules.md` | 增加的是拥有实际边界的 async companion API，不新增只转发参数的浅 wrapper。 |
| `standards/testing.md` | 先写能证明连接池和运行时调用路径的回归测试，再改实现。 |
| `standards/review.md` | 每个 phase 检查 scope、架构、数据库、性能、测试和验证证据。 |

## 4. 非目标

- 不把 Tushare、AKShare、BaoStock 第三方 SDK 强行改成原生 async。
- 不改股票分析业务语义。
- 不改 API response shape。
- 不新增数据库 schema 或 Alembic migration。
- 不新增依赖。
- 不把所有 legacy 同步函数一次性删除。
- 不通过调大 PostgreSQL `max_connections` 掩盖应用侧连接池设计问题。

## 5. 总体依赖图

```text
Phase 0 行为锁定和观测
  -> Phase 1 低风险运行时缓解
  -> Phase 2 模型配置和分析路径异步化
  -> Phase 3 用户、报告、系统路由异步化
  -> Phase 4 数据源配置和 trader flow async companion
  -> Phase 5 Worker/调度器全局并发治理
  -> Phase 6 同步 facade 收口和防误用
  -> Phase 7 全量验证和运行时观测
```

Phase 0 是强依赖。Phase 2 和 Phase 3 可以在 Phase 1 后并行实施，但同一文件不能并行修改。Phase 4 必须在 Phase 2 的配置读取模式稳定后做。Phase 6 必须最后做。

## 6. 文件范围总览

| Phase | 修改源文件 | 新增/修改测试 |
| --- | --- | --- |
| Phase 0 | 不修改业务代码；可新增测试支持 | `backend/tests/unit/app/db/store/test_sync_facade.py`、`backend/tests/unit/app/core/test_postgres_session_state.py`、运行时观测脚本或测试辅助 |
| Phase 1 | `backend/app/core/config.py`、`backend/app/main/application.py`、`docs/database_setup.md`、`deploy/env-templates/*.env.example` | `backend/tests/unit/app/services/scheduler/test_gate.py` |
| Phase 2 | `backend/app/services/config/*`、`backend/app/services/research/agent/provider/client.py`、`backend/app/services/research/agent/stock.py`、`backend/app/services/research/agent/batch/context.py`、`backend/app/services/research/agent/batch/runner.py`、`backend/app/services/analysis/simple/provider.py`、`backend/app/services/analysis/service/execute.py` | 对应 unit/integration tests |
| Phase 3 | `backend/app/services/user.py`、`backend/app/routers/system.py`、`backend/app/routers/reports.py`、`backend/app/services/capability.py`、`backend/app/services/screening/service.py` | user/system/reports/capability/screening tests |
| Phase 4 | `backend/app/core/unified.py`、`backend/app/core/bridge.py`、`backend/app/services/sources/manager.py`、`backend/trader/flows/sources/*.py`、`backend/trader/flows/providers/*/*/common.py` | data source config tests |
| Phase 5 | `backend/app/main/application.py`、`backend/app/services/scheduler/*`、`backend/app/worker/*/sync/*.py`、`backend/app/services/analysis/simple/runner.py` | scheduler/worker/analysis status tests |
| Phase 6 | `backend/app/core/database.py`、`backend/app/db/store/helpers.py`、`backend/app/db/store/sync.py`、`backend/app/db/store/cursor.py` | sync facade guard tests |
| Phase 7 | 不限定 | backend full gate、runtime smoke、PostgreSQL connection observation |

## 6.1 当前 `get_postgres_db_sync()` 调用点清单

检索命令：

```bash
rg -n "get_postgres_db_sync\(" backend/app backend/trader
```

当前代码校验结果：`get_postgres_db_sync(` 仍有 24 处命中，其中包含保留的 sync legacy 方法、mixed companion 边界和 Phase 6 guard 对象。执行改造时必须重新运行检索命令；不要只依赖本文行号，因为本计划正在分阶段更新代码。

当前剩余命中按 review 归类：

| 分类 | 当前文件 | 处理 phase | 处理方式 |
| --- | --- | --- | --- |
| runtime-mixed / legacy guard | `backend/app/core/bridge.py`、`backend/app/core/unified.py`、`backend/app/services/capability.py`、`backend/app/services/screening/service.py`、`backend/app/services/sources/manager.py`、`backend/app/services/research/agent/provider/client.py`、`backend/app/services/research/agent/stock.py`、`backend/app/services/analysis/simple/provider.py` | Phase 2-4 已有 async companion；Phase 6 guard | 保留同步 legacy 方法，但 FastAPI/Web/Worker 主路径不得新增调用。 |
| runtime-mixed / legacy guard | `backend/trader/flows/sources/common.py`、`backend/trader/flows/sources/provider.py`、`backend/trader/flows/providers/china/tushare/common.py`、`backend/trader/flows/providers/us/alpha/common.py` | Phase 4 已有 async companion；Phase 6 guard | 同步方法保留给 CLI/legacy；async runtime 必须调用 async companion。 |
| runtime-mixed / legacy guard | `backend/app/services/market/news/write.py` | Phase 6 guard | `save_news_data_sync()` 当前仅为同步兼容定义；worker/router 调用使用 async `save_news_data()`。 |
| legacy-sync | `backend/trader/flows/interface/setup.py` | Phase 4/6 | CLI/交互 setup 可保留 sync，runtime 禁用。 |
| facade-definition | `backend/app/core/database.py` | Phase 6 | 保留 sync facade，但加文档、guard、连接池影响约束。 |

下表是最初审查快照，用于说明每个原始命中的设计意图；如果当前检索结果与本表行号不一致，以当前检索结果为准。

| 分类 | 文件:行 | 处理 phase | 处理方式 |
| --- | --- | --- | --- |
| runtime-mixed | `backend/trader/flows/sources/provider.py:60` | Phase 4 | 新增 async companion，Web/Worker 调用迁移，sync legacy 保留。 |
| runtime-mixed | `backend/trader/flows/sources/provider.py:189` | Phase 4 | 同上。 |
| runtime-mixed | `backend/trader/flows/sources/provider.py:219` | Phase 4 | 同上。 |
| runtime-mixed | `backend/trader/flows/sources/common.py:66` | Phase 4 | 新增 async companion，保留同步入口。 |
| runtime-mixed | `backend/trader/flows/sources/common.py:399` | Phase 4 | 同上。 |
| runtime-mixed | `backend/trader/flows/sources/common.py:493` | Phase 4 | 同上。 |
| legacy-sync | `backend/trader/flows/interface/setup.py:51` | Phase 4 | 确认调用方；CLI/交互 setup 可保留 sync，runtime 禁用。 |
| legacy-sync | `backend/trader/flows/interface/setup.py:116` | Phase 4 | 同上。 |
| runtime-mixed | `backend/trader/flows/providers/us/alpha/common.py:55` | Phase 4 | token/config 读取新增 async companion。 |
| runtime-mixed | `backend/trader/flows/providers/china/tushare/common.py:38` | Phase 4 | token/config 读取新增 async companion；SDK 调用仍可用 `to_thread`。 |
| runtime-async | `backend/app/services/sources/manager.py:57` | Phase 4 | manager 构造期不阻塞 DB，改 async 加载 priority。 |
| runtime-async | `backend/app/services/user.py:35` | Phase 3 | `UserService` 懒加载 async collection。 |
| runtime-async | `backend/app/services/market/news/write.py:143` | Phase 6 guard | 当前确认为 `save_news_data_sync()` 兼容定义；worker/router 已走 async `save_news_data()`。 |
| runtime-async | `backend/app/services/scheduler/runtime.py:70` | Phase 5 | 已修复：scheduler runtime 状态读取/写入改 async。 |
| runtime-async | `backend/app/services/research/agent/provider/client.py:185` | Phase 2 | provider client 模型候选读取改 async config boundary。 |
| runtime-async | `backend/app/services/research/agent/stock.py:102` | Phase 2 | active system config 读取改 async。 |
| runtime-async | `backend/app/routers/capabilities.py` -> `backend/app/services/capability.py` | Phase 3 | FastAPI capability 路由改用 async companion；同步 `get_model_config()` 保留给 legacy/线程路径。 |
| runtime-async | `backend/app/services/analysis/simple/provider.py:138` | Phase 2 | 新增 async provider resolver。 |
| runtime-async | `backend/app/services/analysis/simple/provider.py:246` | Phase 2 | fallback provider 查询复用 async resolver。 |
| runtime-async | `backend/app/services/analysis/simple/provider.py:319` | Phase 2 | exception fallback 查询复用 async resolver。 |
| runtime-async | `backend/app/services/analysis/simple/runner.py:85` | Phase 5 | 已修复：progress update 通过运行时 event loop 提交 async 更新，不新建 loop。 |
| runtime-async | `backend/app/services/analysis/simple/runner.py:449` | Phase 5 | 已修复：graph progress fallback 走同一 async progress 提交通道。 |
| runtime-async | `backend/app/services/analysis/service/execute.py:60` | Phase 2 | execution service 改 async document store。 |
| runtime-async | `backend/app/services/analysis/service/execute.py:223` | Phase 2 | 同上。 |
| runtime-async | `backend/app/services/screening/enhanced.py` -> `backend/app/services/screening/service.py` | Phase 3 | async screening 路径调用 `run_async()`；同步 `run()` / `_get_universe()` 保留给 legacy。 |
| runtime-mixed | `backend/app/core/bridge.py:82` | Phase 4 | 增加 async provider bridge。 |
| runtime-mixed | `backend/app/core/bridge.py:178` | Phase 4 | 增加 async system config bridge。 |
| runtime-mixed | `backend/app/core/bridge.py:418` | Phase 4 | 增加 async system settings bridge。 |
| runtime-mixed | `backend/app/core/unified.py:297` | Phase 4 | 新增 `async_get_data_source_configs()`。 |
| facade-definition | `backend/app/core/database.py:487` | Phase 6 | 保留 sync facade，但加文档、guard、连接池影响约束。 |
| runtime-async | `backend/app/routers/system.py:153` | Phase 3 | FastAPI route 改 async DB/service。 |
| runtime-async | `backend/app/worker/tushare/sync/models.py:101` | Phase 5 | 已修复：worker progress/status 改 async DB。 |
| runtime-async | `backend/app/routers/reports.py:48` | Phase 3 | reports route 改 async DB/service。 |

调用点覆盖检查：

- Phase 2 覆盖模型配置和分析执行路径：`provider/client.py`、`stock.py`、`analysis/simple/provider.py`、`analysis/service/execute.py`。
- Phase 3 覆盖 FastAPI 用户/系统/报告及相关 service：`user.py`、`system.py`、`reports.py`、`capability.py`、`screening/service.py`。
- Phase 4 覆盖 trader flow、数据源配置、bridge/unified mixed path。
- Phase 5 覆盖 scheduler、worker、runner、news write 长驻任务路径。
- Phase 6 覆盖 facade 定义和防误用。

## 6.2 代码逻辑 Review 修正

这部分是基于当前代码调用链做的方案 review。以下问题不是文档格式问题，而是会影响方案是否真正解决连接池耗尽。

### Finding A：scheduler job 当前通过 `asyncio.run()` 创建新 event loop

证据：

- `backend/app/main/setup.py:22-27` 的 `_run_worker_coroutine()` 使用 `asyncio.run(runner())`。
- `backend/app/main/setup.py:30-153` 的 `run_tushare_*`、`run_akshare_*`、`run_baostock_*` 都是同步 wrapper。
- `backend/app/main/application.py` 将这些同步 wrapper 注册进 `AsyncIOScheduler`。

影响：

- 每次 scheduler job 执行都会创建新的 event loop。
- `backend/app/core/session.py` 按 event loop 缓存 engine，因此这些 job 可能创建新的 PostgreSQL engine/pool。
- 只给 scheduler 加 semaphore 不够；如果 job 仍通过 `asyncio.run()` 执行，连接池放大仍存在。

修正：

- Phase 1 必须新增任务：调度器直接注册 coroutine job，或在 `application.py` 中定义 async wrapper 并 `await` worker coroutine。
- `backend/app/main/setup.py` 的同步 wrapper 只能保留给 CLI/legacy，不应作为 `AsyncIOScheduler` 的默认执行入口。

### Finding B：`PostgresCursor.__iter__` 是隐式同步桥接入口

证据：

- `backend/app/db/store/cursor.py:47-48` 的 `__iter__()` 调用 `_run_blocking(self._window())`。
- 当前 async runtime 中存在 `list(collection.find())` 或 `for item in collection.find()`：
  - `backend/app/core/bridge.py:86`
  - `backend/app/routers/system.py:157`
  - `backend/app/services/research/agent/provider/client.py:189`
  - `backend/trader/flows/sources/models.py:384`
  - `backend/trader/flows/sources/provider.py:65`
  - `backend/trader/flows/sources/provider.py:192`

影响：

- 即使某个文件不直接调用 `get_postgres_db_sync()`，只要同步迭代 `PostgresCursor`，仍会触发 `_run_blocking()` 和 sync loop。
- 改造验收不能只搜索 `get_postgres_db_sync()`。

修正：

- async runtime 中必须改成 `await cursor.to_list(None)` 或 `async for`。
- Phase 0 增加 cursor 同步迭代清单。
- Phase 7 验收增加 runtime async 目录中不得出现 `list(...find())` 或同步 `for ... in ...find()`。

### Finding C：`UserService` 模块级实例会在 import 时触发同步 DB

证据：

- `backend/app/services/user.py:33-36` 构造时调用 `get_postgres_db_sync()`。
- `backend/app/services/user.py:613-614` 定义 `user_service = UserService()`。

影响：

- 只要导入 `app.services.user`，就可能初始化 sync DB facade。
- 这会把连接池问题提前到应用启动/模块导入阶段，不只是请求执行阶段。

修正：

- Phase 3 不仅要把方法改 async，还必须去掉构造期 DB 初始化。
- 全局 `user_service` 可以保留对象，但对象内部必须 lazy async 获取 collection；或者改为通过依赖函数创建/获取 service。

### Finding D：`analysis/service/execute.py` 是同步线程池执行路径，不能机械改 async

证据：

- `backend/app/services/analysis/service/execute.py:15-18` 的 `_execute_analysis_sync_with_progress()` 是同步函数，注释说明在线程池中运行。
- 同文件 `:57-64`、`:220-227` 在线程内同步读取 `system_configs`。

影响：

- 直接把该函数改成 async 可能破坏线程池执行模型。
- 更合适的方案是：进入线程池前在 async 层预取模型配置，或把线程内配置读取隔离成受限 sync legacy adapter。

修正：

- Phase 2.5 必须先追踪调用方，确认执行模型。
- 不允许把同步线程函数简单改成 coroutine 后交给原线程池调用。

### Finding E：`get_provider_and_url_by_model_sync()` 是多个 async 分析链路的间接同步入口

证据：

- `backend/app/services/analysis/simple/provider.py:117` 的 `get_provider_by_model_name_sync()` 调用 `get_provider_and_url_by_model_sync()`。
- `backend/app/services/analysis/simple/runner.py:162-163`、`:562` 调用同步 provider resolver。
- `backend/app/services/research/agent/provider/client.py:248`、`:267`、`:359` 调用同步 provider resolver。
- `backend/app/services/research/agent/stock.py:158`、`:386`、`:830` 间接或直接调用同步 provider resolver。

影响：

- 只改 `_configured_candidate_models()` 不够。
- 必须把 provider resolver 做成 async 主路径，并把所有 async runtime 调用点一起迁移。

修正：

- Phase 2.1/2.4 的 async model config boundary 是核心前置任务。
- Phase 2 验收必须搜索 `get_provider_and_url_by_model_sync(`，确认它只留在 sync legacy/thread path。

## 7. Phase 0：行为锁定和观测

### Task 0.1：建立同步 DB 调用清单

文件：

- 只读命令，不修改业务文件。
- 输出结果记录在本计划执行日志或 phase notes。

步骤：

- [x] 运行：

```bash
rg -n "get_postgres_db_sync\\(" backend/app backend/trader
rg -n "_run_blocking|_get_sync_loop|run_coroutine_threadsafe" backend/app
```

- [x] 将调用点标记为四类：
  - `runtime-async`：FastAPI route、async service、Worker async path。
  - `runtime-mixed`：可能被 async 和 sync 双路径调用。
  - `legacy-sync`：CLI、脚本、同步测试、一次性工具。
  - `unknown`：需要继续追踪调用方。

验收：

- 没有遗漏 `get_postgres_db_sync()` 调用点。
- 每个调用点都能归类。

### Task 0.2：给同步 facade 增加测试型观测

文件：

- 新增：`backend/tests/unit/app/db/test_sync_facade.py`
- 可选修改：测试 fixture 附近的 `conftest.py`

步骤：

- [x] 写测试证明 `SyncPostgresCollection.find_one()` 会调用 `_run_blocking()`。
- [x] 写测试证明 `_get_sync_loop()` 创建的 loop 与当前运行 loop 不同。
- [x] 写测试时 mock `_run_blocking()`，不连接真实 DB。

建议测试断言：

```python
def test_sync_collection_uses_blocking_bridge(monkeypatch):
    calls = []

    def fake_run_blocking(coro):
        calls.append(coro)
        return {"ok": True}

    monkeypatch.setattr("app.db.store.sync._run_blocking", fake_run_blocking)
    collection = SyncPostgresCollection(fake_async_collection)

    assert collection.find_one({"name": "demo"}) == {"ok": True}
    assert len(calls) == 1
```

验证：

```bash
cd backend && conda run -n trader pytest tests/unit/app/db/test_sync_facade.py tests/unit/app/db/test_sync_guard.py
```

验收：

- 测试不访问真实 PostgreSQL。
- 测试失败时能定位同步 facade 是否仍存在阻塞桥接。

### Task 0.3：锁定 async 配置服务现有行为

文件：

- 新增或修改：`backend/tests/unit/app/services/config/test_system_config_async.py`

步骤：

- [x] 用 fake async collection 测试 `SystemConfigMixin.get_system_config()` 调用 `await config_collection.find_one(...)`。
- [x] 覆盖“数据库有 active config”和“数据库无 active config 创建默认配置”两条路径。
- [x] 不真实连接数据库。

验证：

```bash
cd backend && conda run -n trader pytest tests/unit/app/services/config/test_system_config_async.py
```

验收：

- 证明已有 config service 可作为 async 读取边界复用。

### Task 0.4：建立连接数观测命令

文件：

- 不新增脚本时可只记录命令。
- 如需脚本，新增：`backend/scripts/diagnostics/postgres_connections.py`

步骤：

- [x] 使用 SQL 查询记录连接状态：

```sql
select state, application_name, count(*)
from pg_stat_activity
where datname = current_database()
group by state, application_name
order by count(*) desc;
```

- [x] 启动 backend、worker 后记录 baseline。
- [x] 访问 `/api/config/llm`、`/agent?mode=stock` 后记录变化。

验收：

- 每个后续 phase 能用同一观测方式比较连接数。
- 不输出密码、token、Authorization header。

### Task 0.5：建立同步 cursor 迭代清单

文件：

- 只读命令，不修改业务文件。

步骤：

- [x] 运行：

```bash
rg -n "list\([^\\n]*\.find\(|for .* in .*\.find\(" backend/app backend/trader
```

- [x] 将结果分为：
  - `async-runtime`：FastAPI route、async service、Worker coroutine。
  - `sync-legacy`：脚本、CLI、同步工具。
  - `unclear`：需要追踪调用方。

- [x] 对 `async-runtime` 中的调用点，在对应 phase 中改为：

```python
rows = await collection.find(query).to_list(None)
```

或：

```python
async for row in collection.find(query):
    ...
```

验收：

- async runtime 里的 cursor 不再依赖 `PostgresCursor.__iter__()`。
- `PostgresCursor.__iter__()` 仅作为 sync legacy 兼容能力保留。

## 8. Phase 1：低风险运行时缓解

### Task 1.1：降低本地默认连接池风险

文件：

- 修改：`docs/database_setup.md`
- 可选修改：`deploy/env-templates/postgres-pre-read-evidence.env.example`
- 可选修改：`deploy/env-templates/postgres-post-read-smoke.env.example`
- 可选修改：`deploy/env-templates/postgres-rollback-smoke.env.example`

步骤：

- [x] 增加开发环境建议值：

```env
POSTGRES_POOL_SIZE=3
POSTGRES_MAX_OVERFLOW=2
POSTGRES_POOL_TIMEOUT=30
```

- [x] 文档说明：生产环境应根据 Web/Worker 进程数和 PostgreSQL `max_connections` 计算，不直接照抄开发值。

验证：

```bash
rg -n "POSTGRES_POOL_SIZE|POSTGRES_MAX_OVERFLOW" docs deploy/env-templates backend
```

验收：

- 不修改用户本地 `.env`。
- 文档说明连接池是“每个 process/event loop”计算，不误导为全局值。

### Task 1.2：新增重型同步任务全局并发门

文件：

- 修改：`backend/app/main/application.py`
- 或新增深模块：`backend/app/services/scheduler/gate.py`
- 测试：`backend/tests/unit/app/services/scheduler/test_gate.py`

步骤：

- [x] 新增 `SchedulerGate`，内部使用 `asyncio.Semaphore`。
- [x] 区分 job 类型：
  - `heavy_data_sync`：Tushare/AKShare/BaoStock basics/history/financial/news。
  - `light_status`：status check。
  - `quotes_ingestion`：实时行情独立限流。
- [x] 将重型 job 包装为：

```python
async with scheduler_gate.heavy_data_sync():
    await run_tushare_historical_sync(...)
```

- [x] 默认 heavy concurrency 设置为 1。
- [x] 不改变 APScheduler job id、name、cron。

验证：

```bash
cd backend && conda run -n trader pytest tests/unit/app/services/scheduler/test_gate.py
cd backend && conda run -n trader ruff check app/main/application.py app/services/scheduler tests/unit/app/services/scheduler
```

验收：

- 不同 heavy job 不能同时进入执行体。
- status check 不被 heavy job 长时间阻塞，除非它访问同一外部数据源且明确配置为 heavy。

Review 注意：

- 不能只依赖 APScheduler `max_instances=1`，因为它只限制同一 job。
- 不能用全局裸变量散落在 `application.py` 多处；gate 必须是一个拥有并发策略的模块。

### Task 1.3：将 scheduler 注册入口从同步 wrapper 改为 coroutine job

文件：

- 修改：`backend/app/main/application.py`
- 修改或保留：`backend/app/main/setup.py`
- 测试：`backend/tests/integration/app/routers/scheduler/test_nonblocking_market_sync_jobs.py`
- 测试：`backend/tests/integration/app/services/scheduler/test_init.py`

步骤：

- [x] 在 `application.py` 中不再把 `backend/app/main/setup.py` 的同步 `run_tushare_*` wrapper 作为 scheduler job 主入口。
- [x] 直接 import 或延迟 import worker coroutine，例如 `app.worker.tushare.sync.run_tushare_historical_sync`。
- [x] 如果为了避免启动 import 成本，需要 wrapper，wrapper 必须是 async：

```python
async def run_tushare_historical_job():
    run_tushare_historical_sync = getattr(
        importlib.import_module("app.worker.tushare.sync"),
        "run_tushare_historical_sync",
    )
    async with scheduler_gate.heavy_data_sync():
        await run_tushare_historical_sync(incremental=True)
```

- [x] `backend/app/main/setup.py` 的同步 wrappers 保留给 CLI/legacy，但不得被 `AsyncIOScheduler` 使用。
- [x] 不改变 scheduler job id、name、cron、pause 逻辑。

验证：

```bash
cd backend && conda run -n trader pytest tests/integration/app/routers/scheduler/test_nonblocking_market_sync_jobs.py
cd backend && conda run -n trader pytest tests/integration/app/services/scheduler/test_init.py
rg -n "scheduler.add_job\\(\\s*run_(tushare|akshare|baostock)" backend/app/main/application.py
```

验收：

- scheduler 中的重型数据同步 job 是 coroutine job，不通过 `asyncio.run()` 创建新 event loop。
- `backend/app/main/setup.py` 中的 `_run_worker_coroutine()` 不再是应用内 scheduler 默认路径。

## 9. Phase 2：模型配置和分析路径异步化

### Task 2.1：提取 async 模型配置读取边界

文件：

- 修改或新增：`backend/app/services/config/model.py`
- 修改：`backend/app/services/config/__init__.py` 或现有 config service export。
- 测试：`backend/tests/unit/app/services/config/test_model_config.py`

步骤：

- [x] 定义 async 查询方法：

```python
async def get_active_model_configs() -> list[dict[str, Any]]:
    db = get_postgres_db()
    doc = await db.system_configs.find_one({"is_active": True}, sort=[("version", -1)])
    ...
```

- [x] 查询 `llm_providers` 时使用 async cursor。
- [x] 返回值必须是业务需要的 normalized model/provider/base_url/api_key 结构。
- [x] 保留现有 provider alias 规则，例如 `dashscope` 与 `qwen` 兼容。

验证：

```bash
cd backend && conda run -n trader pytest tests/unit/app/services/config/test_model_config.py
cd backend && conda run -n trader pyright
```

验收：

- 模型配置读取不再要求调用方知道 `system_configs` 和 `llm_providers` 的原始集合结构。
- 不新增只转发 `get_postgres_db()` 的浅 wrapper。

### Task 2.2：迁移 research agent provider client

文件：

- 修改：`backend/app/services/research/agent/provider/client.py`
- 测试：`backend/tests/unit/app/services/research/agent/provider/test_client_models.py`

步骤：

- [x] 将 `_configured_candidate_models()` 改为 async 版本，例如 `_configured_candidate_models_async()`。
- [x] 所有调用它的 async 路径改为 `await`。
- [x] 如果存在纯 sync 调用方，保留 sync legacy 函数，但标记只给 CLI/legacy 用。
- [x] fallback 到环境变量的语义保持不变。

验证：

```bash
cd backend && conda run -n trader pytest tests/unit/app/services/research/agent/provider/test_client_models.py
cd backend && conda run -n trader pyright
```

验收：

- Web/Agent provider path 不调用 `get_postgres_db_sync()`。
- provider fallback 仍能在 DB 无配置时使用环境变量或默认 base URL。

### Task 2.3：迁移 stock agent 模型配置读取

文件：

- 修改：`backend/app/services/research/agent/stock.py`
- 修改：`backend/app/services/research/agent/batch/context.py`
- 修改：`backend/app/services/research/agent/batch/runner.py`
- 测试：`backend/tests/unit/app/services/research/agent/test_stock_async_models.py`
- 测试：`backend/tests/unit/app/services/research/agent/batch/test_runner.py`
- 测试：`backend/tests/unit/app/services/research/agent/tool/test_calls.py`
- 测试：`backend/tests/unit/app/services/research/agent/tool/test_registry.py`

步骤：

- [x] 新增 `_load_active_system_config_doc_async()`，Web/Agent runtime 使用 async helper；同步 `_load_active_system_config_doc()` 暂留给 legacy 同步调用链。
- [x] 将 `_enabled_llm_configs()` 保持纯函数，不访问 DB。
- [x] 新增 `_resolve_analysis_models_async()`、`_analysis_parameters_async()`、`_missing_model_keys_async()`。
- [x] `StockAnalysisWorkflow.run_single()` 改为 await async 参数解析和缺 key 检查。
- [x] `run_agent_stock_workflow()` await async workflow context 构造。
- [x] `build_agent_stock_workflow_context()` 改为 async，并使用已解析 provider info 调用 `create_analysis_config_async()`，避免重复同步 resolver。
- [x] `_record_stock_workflow_usage()` 改为 async provider/pricing 查询。
- [x] `batch/runner.py` 改为调用 `build_batch_request_context_async()`，避免 batch runtime 继续复用同步 stock 参数解析。
- [x] 保持 stock tool payload、`task_id`、`analysis_id`、links 字段不变。

验证：

```bash
cd backend && conda run -n trader pytest tests/unit/app/services/research/agent/test_stock_async_models.py
cd backend && conda run -n trader pytest tests/unit/app/services/research/agent/tool/test_calls.py tests/unit/app/services/research/agent/tool/test_registry.py tests/unit/app/services/research/agent/batch/test_runner.py
```

验收：

- `stock.py` 的 Web/Agent 分析路径不再通过同步 facade 读取 active system config。
- `batch_stock_analysis` runtime 不再通过同步 `_analysis_parameters()` 间接读取模型配置。
- 缺少 `symbol` / `stock_code` 的 payload 在查询模型配置前直接返回参数错误。

### Task 2.4：迁移 simple analysis provider

文件：

- 修改：`backend/app/services/analysis/simple/provider.py`
- 测试：`backend/tests/unit/app/services/analysis/simple/test_provider.py`

步骤：

- [x] 新增 async 查询函数 `get_provider_and_url_by_model(...)`。
- [x] 保留 `get_provider_and_url_by_model_sync(...)`，仅用于明确同步调用链。
- [x] async 分析 runner/service 主路径全部调用 async 版本或线程前 async 预取；`analysis/service/execute.py` 和 `analysis/simple/runner.py` 均已完成。
- [x] 将 provider/base_url/api_key fallback 逻辑收敛到 `_build_provider_info(...)`，避免 async/sync 两套规则继续分叉。

验证：

```bash
cd backend && conda run -n trader pytest tests/unit/app/services/analysis/simple/test_provider.py
cd backend && conda run -n trader pyright
```

验收：

- async 分析路径不再因为模型配置查询创建 sync loop。
- sync 版本没有被 Web/Worker 新代码调用。

Review 注意：

- 不能只因为 async helper 已存在就判定本任务完成。追加 review 曾证明 `SimpleAnalysisService` 也是 Web/Worker 主路径：`backend/app/services/analysis/simple/task.py` 通过共享线程池执行 `backend/app/services/analysis/simple/runner.py`，原实现在线程内调用 `get_provider_and_url_by_model_sync()`。
- 线程内同步调用虽然不会触发 running-loop guard，但仍会创建/复用 sync facade 后台 loop 和额外 DB 连接池，因此 Web/Worker 主路径不能把它归为普通 legacy。该缺口已在 Task 2.6 修复：线程前 async 解析模型/provider 上下文，线程内只消费 `SimpleAnalysisThreadContext`；sync helper 仅保留给 legacy fallback。

### Task 2.5：迁移 analysis service execute

文件：

- 修改：`backend/app/services/analysis/service/execute.py`
- 测试：`backend/tests/unit/app/services/analysis/service/test_execute.py`

步骤：

- [x] 先追踪 `_execute_analysis_sync_with_progress()` 的调用方，确认它仍通过 `_execute_single_analysis_async()` 的 `run_in_executor(...)` 在线程池中运行。
- [x] 保持线程池模型，不把该函数直接改成 async。
- [x] 在进入线程池前的 async 层预取 quick/deep model config、provider info 和 normalized provider，封装为 `AnalysisThreadModelContext` 后传入同步执行函数。
- [x] 线程函数不再读取 PostgreSQL；未传 `AnalysisThreadModelContext` 时仅走 `_legacy_thread_model_context()` 兼容路径。
- [x] 确认状态写入、任务读取、报告关联字段保持原样。

验证：

```bash
cd backend && conda run -n trader pytest tests/unit/app/services/analysis/service/test_execute.py
```

验收：

- async service 编排路径中没有不必要的同步 DB bridge。
- 线程池内部不再读取 PostgreSQL 模型配置；保留的 sync provider helper 仅在 legacy context fallback 中使用，Phase 6 继续收口。
- 未改变 analysis task contract。

### Task 2.6：迁移 SimpleAnalysisService 线程池前模型和股票名解析

文件：

- 修改：`backend/app/services/analysis/simple/base.py`
- 修改：`backend/app/services/analysis/simple/provider.py`
- 修改：`backend/app/services/analysis/simple/runner.py`
- 修改：`backend/app/services/analysis/simple/task.py`
- 测试：`backend/tests/unit/app/services/analysis/simple/test_runner_status.py`
- 测试：`backend/tests/unit/app/services/analysis/simple/test_provider.py`

修复前代码证据：

- `backend/app/services/analysis/simple/base.py` 曾固定创建 `ThreadPoolExecutor(max_workers=3)`；这也是后台显示“最大并发 3”的来源之一。
- `backend/app/services/analysis/simple/task.py:431` 通过 `loop.run_in_executor(...)` 调用 `_run_analysis_sync()`。
- `backend/app/services/analysis/simple/runner.py` 在线程内调用 `get_provider_and_url_by_model_sync()`。
- `backend/app/services/analysis/simple/task.py:49`、`:67` 在 async 请求/worker 编排中同步调用 `_resolve_stock_name()`；`_resolve_stock_name()` 会进入 `backend/app/services/analysis/simple/provider.py` 的 `_get_stock_info_safe()`，再走同步 data source manager。
- `/api/analysis/analyze` 入队后由 `backend/app/worker.py:109` 或 `backend/app/worker/analysis.py:202` 调用 `SimpleAnalysisService.execute_analysis_background()`，因此这不是纯 CLI legacy。

步骤：

- [x] 新增 simple runner 专用的线程上下文 `SimpleAnalysisThreadContext`，包含 quick/deep model、provider info 和模型配置。
- [x] 在 `_execute_analysis_sync()` 进入 `run_in_executor(...)` 前 await async provider/config 解析，并把 context 传入 `_run_analysis_sync()`。
- [x] `_run_analysis_sync()` 和 `create_analysis_config()` 调用优先使用传入的 provider info；Web/Worker 主路径不再在线程内同步查询 provider。
- [x] 错误上下文中需要 provider/backend_url 时，优先使用线程前已解析 context；不再为了错误格式化重新同步查 DB。
- [x] 增加 async 股票名解析 `_resolve_stock_name_async()`，在 `create_analysis_task()` 中 await；同步 `_resolve_stock_name()` 仅保留给 legacy 同步列表补全。
- [x] simple runner 的 `max_workers=3` 已改为 `ANALYSIS_MAX_WORKERS`，默认仍为 3，并写入 `backend/.env.example`。

验证：

```bash
cd backend && conda run -n trader pytest tests/unit/app/services/analysis/simple/test_runner_status.py tests/unit/app/services/analysis/simple/test_provider.py -q
cd backend && conda run -n trader ruff check app/services/analysis/simple tests/unit/app/services/analysis/simple
cd backend && conda run -n trader pyright app/services/analysis/simple tests/unit/app/services/analysis/simple
```

验收：

- `rg -n "get_provider_and_url_by_model_sync\\(" backend/app/services/analysis/simple` 只能命中同步 legacy helper 或未被 Web/Worker 主路径调用的兼容分支。
- `SimpleAnalysisService.execute_analysis_background()` 的 Web/Worker 路径不再为了模型/provider 或股票名称读取进入 sync facade。
- 后台最大并发的来源、默认值和配置入口清晰一致。

当前验证：

```text
conda run -n trader pytest tests/unit/app/services/analysis/simple/test_runner_status.py tests/unit/app/services/analysis/simple/test_provider.py tests/unit/app/services/analysis/service/test_execute.py -q
10 passed, 1 warning

conda run -n trader ruff check app/core/config.py app/services/analysis/simple tests/unit/app/services/analysis/simple
All checks passed

conda run -n trader pyright app/core/config.py app/services/analysis/simple tests/unit/app/services/analysis/simple
0 errors, 0 warnings, 0 informations
```

## 10. Phase 3：用户、报告、系统路由异步化

### Task 3.1：迁移 UserService

文件：

- 修改：`backend/app/services/user.py`
- 测试：`backend/tests/unit/app/services/test_user.py` 或镜像路径 `backend/tests/unit/app/services/user/test_service.py`

步骤：

- [x] `UserService.__init__()` 不再立即调用 `get_postgres_db_sync()`。
- [x] 增加 async `_users_collection()`，内部使用 `get_postgres_db()`。
- [x] `create_user()` 中的 `find_one()`、`insert_one()` 全部改为 `await`。
- [x] `authenticate_user()` 中的 `update_one()` 改为 `await`。
- [x] `update_user()`、`get_user_by_id()`、`get_user_by_username()` 中所有 collection 调用改为 `await`。
- [x] 保留密码 hash 和 dual write 语义；新增 `set_admin()` 让 account route 不直接访问 service 内部 DB。

验证：

```bash
cd backend && conda run -n trader pytest tests/unit/app/services/test_user.py
cd backend && conda run -n trader pyright
```

验收：

- async auth/user route 不会在构造 UserService 时创建 sync DB loop。
- 用户创建、登录、更新行为保持不变。

Review 注意：

- 不要把用户不存在、密码错误、DB 错误都吞成无法区分的静默成功。
- 不要在 service helper 中自行 `commit()`，沿用 document store 现有写入契约。

### Task 3.2：迁移 system router

文件：

- 修改：`backend/app/routers/system.py`
- 测试：`backend/tests/integration/app/routers/test_system.py`

步骤：

- [x] 替换 route 内 `get_postgres_db_sync()` 为 async DB。
- [x] 原始 provider 文档查询改为 `await providers_collection.find().to_list(None)`。
- [x] API response shape 保持不变。

验证：

```bash
cd backend && conda run -n trader pytest tests/integration/app/routers/test_system.py
```

验收：

- API response shape 和状态码不变。
- route 不再包含同步 DB facade。

### Task 3.3：迁移 reports router

文件：

- 修改：`backend/app/routers/reports.py`
- 测试：`backend/tests/integration/app/routers/reports/`

步骤：

- [x] 替换 `get_postgres_db_sync()` 为 async DB。
- [x] `get_stock_name()` 改为 async，并使用 `get_data_source_configs_async()`。
- [x] 保持 `_id`、`analysis_id`、`task_id` lookup 兼容性。
- [x] 确认用户隔离条件不丢失。
- [x] 大列表查询保持现有分页和边界，不新增无界查询。

验证：

```bash
cd backend && conda run -n trader pytest tests/integration/app/routers/reports
```

验收：

- report list/detail 行为不变。
- 不新增数据越权风险。

### Task 3.4：迁移 capability 和 screening

文件：

- 修改：`backend/app/services/capability.py`
- 修改：`backend/app/services/screening/service.py`
- 关联依赖：`backend/trader/flows/sources/cache.py`
- 关联依赖：`backend/trader/flows/sources/common.py`
- 测试：对应 service unit tests。

步骤：

- [x] 追踪调用方是否 async：`capabilities.py` 是 FastAPI async route；`enhanced.py` 是 async screening route service；`analysis/simple/runner.py` 仍是线程/legacy 相关路径。
- [x] capability 新增 `get_model_config_async()`、`validate_model_pair_async()`、`recommend_models_for_depth_async()`，FastAPI route 改为 await async companion。
- [x] screening 新增 `run_async()` 和 `_get_universe_async()`，`EnhancedScreeningService` 的传统 fallback 改为 await async screening path。
- [x] 同步 `get_model_config()`、`run()`、`_get_universe()` 保留为 legacy adapter，避免破坏同步调用方。

验证：

```bash
cd backend && conda run -n trader pytest tests/unit/app/services
```

验收：

- Web runtime 中 capability/screening 查询不使用 sync facade。
- 对 screening 不能只验证 `_get_universe_async()`；`run_async()` 后续调用的 `_run_with_symbols()` 也必须不通过 `get_data_source_manager()` 构造期同步读取 DB。
- `rg` 仍会在 `capability.py` 和 `screening/service.py` 命中 sync facade，但这些命中属于保留的同步 legacy 方法；判断是否遗漏必须结合调用方，而不是只看文本命中。

## 11. Phase 4：数据源配置和 trader flow async companion

### Task 4.1：为 unified config 增加 async 数据源配置读取

文件：

- 修改：`backend/app/core/unified.py`
- 测试：`backend/tests/unit/app/core/test_unified_data_sources.py`

步骤：

- [x] 保留现有 `get_data_source_configs()` 同步方法。
- [x] 保留/使用现有 `get_data_source_configs_async()`。
- [x] async 方法使用 `get_postgres_db()`，并复用现有 hardcoded fallback。
- [x] fallback 行为和排序规则保持一致。
- [x] `get_unified_system_config()` 改为 await `get_data_source_configs_async()`，避免 async fallback 再走同步数据源配置读取。

验证：

```bash
cd backend && conda run -n trader pytest tests/unit/app/core/test_unified_data_sources.py
```

验收：

- Web/Worker 可以调用 async 方法。
- legacy sync 调用方不破坏。

### Task 4.2：为 config bridge 增加 async provider/data-source bridge

文件：

- 修改：`backend/app/core/bridge.py`
- 测试：`backend/tests/unit/app/core/test_bridge.py`

步骤：

- [x] 找出 `bridge.py` 中三处 `get_postgres_db_sync()` 调用。
- [x] 对运行时调用方增加 async companion：`bridge_config_to_env_async()` 和 `reload_bridged_config_async()`。
- [x] 以 `bridge_config_to_env_async()` / `reload_bridged_config_async()` 承载 async runtime bridge；原 sync 方法保留给 CLI/legacy。
- [x] `app/main/application.py`、`app/routers/system.py`、`app/routers/config/setup.py` 已切到 async bridge。
- [x] 不改变 provider alias 和 env 优先级规则；provider/data source/system settings 读取使用 async document store。

验证：

```bash
cd backend && conda run -n trader pytest tests/unit/app/core/test_bridge.py
```

验收：

- async runtime 不再需要通过 bridge 的 sync 方法读取 DB。

### Task 4.3：迁移 data source manager

文件：

- 修改：`backend/app/services/sources/manager.py`
- 测试：`backend/tests/unit/app/services/sources/test_manager.py`

步骤：

- [x] 将 `_load_priority_from_database()` 拆出 async 版本 `load_priority_from_database_async()`。
- [x] manager 初始化不再主动加载 priority，不再因自身 priority 读取触发 sync DB。
- [x] `app/routers/sources.py` 通过 `_new_data_source_manager()` await priority 加载。
- [x] `trader` provider 构造期 token 读取仍属于 Task 4.4；Tushare async `connect()` 已处理，Tushare sync token loader 作为 `connect_sync()` legacy 路径保留。

验证：

```bash
cd backend && conda run -n trader pytest tests/unit/app/services/sources/test_manager.py
```

验收：

- 构造 manager 不创建 sync DB loop。
- 数据源 priority 规则保持不变。

### Task 4.4：为 trader flow 数据源模块增加 async companion

文件：

- 修改：`backend/trader/flows/sources/provider.py`
- 修改：`backend/trader/flows/sources/common.py`
- 修改：`backend/trader/flows/sources/cache.py`
- 修改：`backend/trader/flows/sources/summary.py`
- 修改：`backend/trader/flows/interface/setup.py`
- 修改：`backend/trader/flows/providers/china/tushare/common.py`
- 修改：`backend/trader/flows/providers/us/alpha/common.py`
- 测试：`backend/tests/unit/trader/flows/sources/`、`backend/tests/unit/trader/flows/providers/`

步骤：

- [x] 不删除现有 sync 方法。
- [x] 为 DB 配置读取新增 async companion；China/US priority 与 availability async loader 已完成，sync legacy loader 保留。
- [x] `DataSourceManager()` 和 `USDataSourceManager()` 构造期不得读取 sync DB；DB 配置加载改为显式 sync legacy loader 或 async companion。
- [x] `get_data_source_manager()` / `get_us_data_source_manager()` 保留同步 legacy 语义；新增 async 获取入口，供 Web/Worker 使用。
- [x] Web/Worker 调用方迁移到 async companion，包括 screening、quotes ingestion、market sync source、stocks fallback、research/simple provider 中的 trader manager 调用；research/simple provider 的同步 stock-name helper 已按 Task 2.6 改为 async path。
- [x] `trader/flows/providers/china/tushare/common.py` 已新增 `_get_token_from_database_async()`，async `connect()` 不再调用同步 token loader；`connect_sync()` 保持同步 loader。
- [x] `trader/flows/providers/us/alpha/common.py` 已新增 `get_api_key_async()`，async runtime 可绕开同步 token loader。
- [x] `trader/flows/sources/models.py` 已新增 `get_stock_basic_info_async()`，全量股票列表读取使用 async cursor；同步 `get_stock_basic_info()` 保留 legacy 语义。
- [x] CLI/脚本保留 sync 方法。
- [x] Tushare/AKShare SDK 阻塞调用继续通过 `asyncio.to_thread()` 或现有隔离方式处理，不强行改 SDK。

验证：

```bash
cd backend && conda run -n trader pytest tests/unit/trader/flows/sources tests/unit/trader/flows/providers
```

验收：

- trader flow 同步入口仍可运行。
- Web/Worker 不再为了读取数据源 token/priority 进入 sync DB facade。
- Web/Worker 不再为了补股票名称进入同步 data source manager；该验收由 Task 2.6 覆盖。
- `backend/tests/unit/trader/flows/sources/test_manager_async.py` 中“构造器不调用 sync DB”和“async priority order”回归测试必须通过。

Review 注意：

- 不能把所有函数签名直接改成 async，否则会破坏 CLI 和同步测试。
- async companion 必须拥有真实配置读取语义，不只是浅转发。
- 当前代码证据显示，仅在 provider 层新增 async token loader 不够；`DataSourceManager.__init__()`、`USDataSourceManager.__init__()`、全局 manager cache、以及调用这些 manager 的 Web/Worker 入口都必须纳入本 Task。

## 12. Phase 5：Worker 和调度器全局并发治理

### Task 5.1：迁移 analysis simple runner 的状态更新

文件：

- 修改：`backend/app/services/analysis/simple/runner.py`
- 测试：`backend/tests/unit/app/services/analysis/simple/test_runner_status.py`

步骤：

- [x] 移除“创建新 event loop 更新状态”的路径。
- [x] 在已有运行 loop 中提交 `_update_progress_async(...)`。
- [x] PostgreSQL `analysis_tasks.update_one(...)` 改为 async。
- [x] 对确实没有 running loop 的 legacy 路径，不再隐式创建新 loop 或调用 sync DB，而是记录 debug 并跳过异步状态写入。

验证：

```bash
cd backend && conda run -n trader pytest tests/unit/app/services/analysis/simple/test_runner_status.py
```

验收：

- runner 不再因为状态更新创建额外 event loop。
- 状态更新失败时可观察，不伪装成任务成功。

### Task 5.2：迁移 worker tushare sync models

文件：

- 修改：`backend/app/worker/tushare/sync/models.py`
- 测试：`backend/tests/unit/app/worker/tushare/sync/test_models.py`

步骤：

- [x] 将 worker async path 中的 `sync_db` 替换为 async DB。
- [x] 保留现有 worker async 调用模型，不新增同步脚本入口。
- [x] 保持任务进度字段和统计字段不变。

验证：

```bash
cd backend && conda run -n trader pytest tests/unit/app/worker/tushare/sync/test_models.py
```

验收：

- worker 长驻进程不再因为 progress write 创建 sync loop。

### Task 5.2a：迁移 scheduler runtime progress

文件：

- 修改：`backend/app/services/scheduler/runtime.py`
- 测试：`backend/tests/unit/app/services/scheduler/test_runtime.py`

步骤：

- [x] `update_job_progress()` 内的执行记录查询改为 async document store。
- [x] progress update / insert 改为 await async collection 方法。
- [x] `cancel_requested` 时继续抛出 `TaskCancelledException`，不能被宽泛异常吞掉。
- [x] 删除无实际作用的动态 `AsyncIOScheduler` 导入。

验证：

```bash
cd backend && conda run -n trader pytest tests/unit/app/services/scheduler/test_runtime.py -q
```

验收：

- scheduler runtime progress 不再调用 `get_postgres_db_sync()`。
- 用户取消任务时，调用方仍能感知取消异常。

### Task 5.3：给长循环外部调用加有界并发和批次策略审查

文件：

- `backend/app/worker/tushare/sync/base.py`
- `backend/app/services/market/historical.py`
- AKShare/BaoStock 对应 sync service 文件。

步骤：

- [x] 审查每个按 symbol 循环的地方是否串行、并发或批量。
- [x] 保留外部 SDK rate limit。
- [x] DB 写入批次使用已有 bulk/upsert 边界。
- [x] 不在打开 DB transaction 的情况下等待慢外部 API。

验证：

```bash
cd backend && conda run -n trader pytest tests/unit/app/worker tests/unit/app/services/market
```

验收：

- 没有全量 symbol 级无界 `asyncio.gather()`；`backend/app/worker/tushare/sync/common.py` 的 gather 被 `batch_size` 限制。
- 没有发现慢外部调用包在显式 DB transaction 内。
- `backend/app/services/market/news/write.py` 的 `save_news_data_sync()` 是同步兼容定义；当前 worker/router 调用走 async `save_news_data()`。

## 13. Phase 6：同步 facade 收口和防误用

### Task 6.1：标记 sync facade 使用边界

文件：

- 修改：`backend/app/core/database.py`
- 修改：`backend/app/db/store/helpers.py`
- 测试：`backend/tests/unit/app/db/test_sync_guard.py`

步骤：

- [x] 为 `get_postgres_db_sync()` 增加文档注释：仅允许 CLI、脚本、legacy sync path。
- [x] 增加环境可控 guard：
  - 开发/测试中，如果在 running event loop 内调用 sync facade，发出 warning 或抛出明确错误。
  - legacy 明确允许时通过参数或上下文 manager 放行。
- [x] 日志不得包含连接串密码。

验证：

```bash
cd backend && conda run -n trader pytest tests/unit/app/db/test_sync_guard.py
```

验收：

- 新代码在 async runtime 误用 sync facade 会被测试捕获。
- 已缓存的 sync DB 继续调用 `_run_blocking()` 或同步 cursor 迭代时，也会被 guard 捕获。

### Task 6.2：限制 sync facade 连接池影响

文件：

- 修改：`backend/app/core/session.py`
- 或新增专用 sync facade session 配置边界。

步骤：

- [x] 评估是否给 sync facade 独立配置小池：

```env
POSTGRES_SYNC_POOL_SIZE=1
POSTGRES_SYNC_MAX_OVERFLOW=1
```

- [x] 当前不实现独立 sync pool 配置；sync facade 仍复用 async document-store bridge，不引入新的同步 SQLAlchemy engine 或第二套配置面。
- [x] 通过 Phase 6.1 guard 确保长驻 async runtime 不使用 sync facade；CLI/脚本/legacy 同步边界需要显式放行。

验证：

```bash
cd backend && conda run -n trader pytest tests/unit/app/core/test_session.py tests/unit/app/db/test_sync_guard.py
```

验收：

- sync facade 不再能在长驻进程中悄悄放大连接池。
- 不新增 `POSTGRES_SYNC_POOL_SIZE` / `POSTGRES_SYNC_MAX_OVERFLOW`，避免扩大配置和运行时分支；连接池放大风险由 async-runtime guard 控制。

Review 注意：

- 不要引入同步 SQLAlchemy engine 作为新依赖方向，除非明确证明比现有 async bridge 更简单且风险更低。
- 不要把 session cache 从 per-loop 改成全局单例，除非完整验证跨 loop SQLAlchemy async engine 安全性。

## 14. Phase 7：验证和发布前检查

### Task 7.1：静态检查

命令：

```bash
cd backend && conda run -n trader ruff check app tests
cd backend && conda run -n trader pyright
rg -n "get_provider_and_url_by_model_sync\\(" backend/app backend/trader
rg -n "list\\([^\\n]*\\.find\\(|for .* in .*\\.find\\(" backend/app backend/trader
```

验收：

- 不新增 Ruff 错误。
- 不新增 Pyright 错误或 warning。
- `get_provider_and_url_by_model_sync(` 只出现在明确 sync legacy 或线程池隔离路径。
- async runtime 中不存在同步 cursor 迭代。

### Task 7.2：后端测试

命令：

```bash
cd backend && conda run -n trader pytest tests/unit/app/db/store
cd backend && conda run -n trader pytest tests/unit/app/services/config
cd backend && conda run -n trader pytest tests/unit/app/services/research/agent
cd backend && conda run -n trader pytest tests/unit/app/services/analysis
cd backend && conda run -n trader pytest tests/integration/app/routers/reports
cd backend && conda run -n trader pytest
```

验收：

- targeted tests 先通过。
- 最后必须跑全量 `pytest`，不能跳过。

### Task 7.3：运行时 smoke

步骤：

- [x] 启动 backend。
- [x] 启动 worker。
- [x] 打开 `/docs`，确认 200。
- [x] 打开 `/agent?mode=stock`，确认页面 200。
- [x] 登录态请求 `/api/config/llm`，确认 200 且响应耗时没有异常飙升。
- [x] 创建或读取一个分析任务状态，确认没有 `TooManyConnectionsError`。
- [x] 观察 PostgreSQL 连接状态。

命令示例：

```bash
psql -h localhost -U tradingagents -d trading_agents_cn -c "
select state, application_name, count(*)
from pg_stat_activity
where datname = current_database()
group by state, application_name
order by count(*) desc;"
```

验收：

- 后端日志没有 `asyncpg.exceptions.TooManyConnectionsError`。
- `/api/config/llm` 不再因为 DB 连接耗尽出现 13s 以上阻塞。
- backend + worker 稳态连接数符合池配置预期。

当前运行时证据：

```text
backend: python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
worker: python -m app.worker.analysis
frontend: next-server

GET /docs -> 200, 0.002454s
GET /agent?mode=stock -> 200, 0.032667s
GET /api/config/llm without auth -> 401, expected auth boundary
POST /api/auth/login using dev default admin -> success
GET /api/config/llm with auth -> 200, 1.338603s
GET /api/analysis/tasks/{task_id}/status with auth -> 200, 0.845028s
Backend reload after mapper fix -> /docs 200, /api/health 200
market_quotes document-store smoke -> 1 specialized row, legacy_id=market_quotes:codex_smoke:CDXSMOKE1, close=2.340000
post-reload log check -> no uq_market_quotes_legacy_id, no market_quotes status=failed, no TooManyConnectionsError

PostgreSQL pg_stat_activity:
idle=4
idle in transaction=1
active psql observer=1
```

结论：连接池/同步封装改造相关 smoke 通过，未观察到 `TooManyConnectionsError`。本轮 runtime smoke 曾观察到 `market_quotes.legacy_id` 唯一键冲突导致的 dual-write warning；后续 root-cause 证明问题来自 `market_quotes` 专用表 mapper 在 document-store 自动双写路径中优先使用随机 `_id` 作为 `legacy_id`。当前已修复为按 `(source, code)` 生成稳定业务 legacy id，并用回归测试和真实 DB smoke 锁定；backend reload 后日志复核未再观察到同类 warning。

## 15. 执行顺序建议

优先执行：

1. Phase 0：先补测试和观测。
2. Phase 1：连接池配置文档 + scheduler gate，快速降低风险。
3. Phase 2：模型配置和分析路径，这是当前 UI 报错最相关路径。
4. Phase 3：用户/报告/系统 route，减少 Web request 中的 sync facade。
5. Phase 4：trader flow async companion。代码 review 证明 screening、quotes、stocks fallback 会间接进入 trader manager，因此不能放到 Phase 5 后。
6. Phase 5：runner/worker 状态写入，减少长驻 worker sync loop。
7. Phase 6：guard 和收口，防止未来回退。
8. Phase 7：全量验证。

不建议先执行：

- 直接删除 `get_postgres_db_sync()`。
- 直接把 `trader/flows` 所有函数签名改成 async。
- 直接把第三方 SDK 调用改造成伪 async。
- 只调大 PostgreSQL `max_connections`。

## 16. 自审 Review

### 16.1 Scope Review

结论：通过。

- 计划只处理 PostgreSQL 同步 facade、async 运行时、调度并发和相关测试。
- 没有包含 crypto/web3、UI 视觉、股票分析业务扩展、数据 schema 变更。
- 没有要求 commit/push。

### 16.2 Architecture Review

结论：通过，但 Phase 4 风险最高。

- Web/Worker async path 迁移到 async DB，符合 database standard。
- legacy sync path 通过 companion API 保留，避免破坏 CLI。
- Phase 4 必须逐调用方迁移，不能机械改签名。

### 16.3 Database Review

结论：通过。

- 不新增 schema，不需要 Alembic migration。
- 不改变 transaction ownership。
- 计划明确避免 async request 中混入 blocking DB。
- 连接池问题同时通过配置、调度 gate、sync facade 收口三层处理。

### 16.4 Performance Review

结论：通过。

- 不以增加并发解决问题，而是减少重复池和阻塞。
- 调度器增加全局 heavy job gate，补上 APScheduler `max_instances=1` 的不足。
- 外部 SDK 保留 `to_thread`/隔离策略，避免阻塞 event loop。

### 16.5 Testing Review

结论：已补齐全量后端验证和运行时 smoke；后续只应针对新增改动重跑相应 gate。

- 每个 phase 都列出对应测试位置和命令。
- Phase 7 明确要求全量 backend pytest，不能只跑 targeted tests；本轮已修正 `backend/pyproject.toml` 的默认 deselect 配置，并完成无 deselect 的全量 pytest。
- 计划未要求真实外部 API、真实 token 或生产 DB。
- 已补 `test_stock_async_models.py` 锁定 stock async 路径不调用同步 provider/config resolver。
- 已复跑 stock/provider/tool/batch 相关 targeted tests。
- 当前全量结果：`conda run -n trader pytest` -> `647 passed, 3 warnings in 336.92s`。

### 16.6 Contradiction Review

结论：原文存在一处执行顺序矛盾，已修正。

- “改 async”与“保留 sync facade”不矛盾：前者针对 Web/Worker runtime，后者针对 CLI/legacy。
- “不新增浅 wrapper”与“新增 async companion”不矛盾：companion API 必须拥有配置读取、fallback、normalization 等真实边界职责。
- “降低连接池配置”与“改 async 调用”不矛盾：配置是短期风险缓解，async 化是结构性修复。
- 依赖图要求 Phase 4 在 Phase 5 前，原执行顺序建议却把 Phase 5 放在 Phase 4 前；当前代码 review 证明 trader manager 会被 screening、quotes、stocks fallback 等 Web/Worker 路径间接调用，因此 Phase 4 必须先于 Phase 5 收口。

### 16.7 Missing Risk Review

已覆盖风险：

- 连接池按 event loop 放大。
- scheduler 不同 job 全局并发未限制。
- 第三方 SDK 阻塞调用不能原生 async。
- trader flow 同步兼容性。
- CLI/脚本兼容性。
- API contract 稳定。
- 全量 pytest 验证。

仍需继续按新增改动复查：

- 每个 `get_postgres_db_sync()` 调用点的真实调用方是否全部归类正确。
- 当前测试目录是否已有可复用 fixture，避免重复造 fixture。
- 本地 `.env` 是否覆盖了连接池和同步任务开关；本轮 runtime smoke 已使用 backend `.env` 观测 PostgreSQL 连接状态。

## 17. 当前代码校验 Review 结果

本节记录截至当前执行点的代码逻辑 review 结果，防止把“计划”误读为“全部已完成”。

### 17.1 已确认并已修正

- `backend/app/main/application.py` 的 scheduler heavy job 已改为 coroutine wrapper，并通过 `SchedulerGate` 做全局 heavy gate；不再把 `backend/app/main/setup.py` 的 `asyncio.run()` 同步 wrapper 作为 `AsyncIOScheduler` 主入口。
- `backend/app/services/analysis/simple/provider.py` 已新增 async `get_provider_and_url_by_model()` 和 `create_analysis_config_async()`；async builder 支持复用已解析 provider info，避免重复查询。simple runner 主路径已按 Task 2.6 切到线程前 async 解析。
- `backend/app/services/research/agent/provider/client.py` 的 Agent 模型解析和 diagnostics 已迁移到 async provider/config path。
- `backend/app/services/research/agent/stock.py` 的 single-stock runtime 已迁移到 async 模型解析、async provider 缺 key 检查、async workflow context 构造、async usage pricing。
- `backend/app/services/research/agent/batch/runner.py` 已改为使用 `build_batch_request_context_async()`；batch runtime 不再复用同步 `_analysis_parameters()`。
- `StockAnalysisWorkflow.run_single()` 已调整校验顺序：缺少 `symbol` / `stock_code` 时先返回参数错误，不再提前查询模型配置。
- `backend/app/services/analysis/service/execute.py` 的线程池执行路径已改为线程前 async 预取 `AnalysisThreadModelContext`，线程内不再读取 PostgreSQL 模型配置。
- `backend/app/services/user.py` 构造期不再初始化 sync DB，用户 CRUD 路径改为 async collection，`account.py` 管理员设置通过 service 方法完成。
- `backend/app/routers/system.py` 的 provider 原始配置读取改为 async cursor。
- `backend/app/routers/reports.py` 的股票名称补全改为 async DB 和 async data source config。
- `backend/app/services/capability.py` 已新增 async companion；`backend/app/routers/capabilities.py` 的 recommend/validate/model detail 改为 await async 方法。
- `backend/app/services/screening/service.py` 已新增 `run_async()` / `_get_universe_async()`；`EnhancedScreeningService` 的 async route fallback 不再调用同步股票池。
- `backend/app/core/unified.py` 的 `get_unified_system_config()` 已改为 await async 数据源配置读取。
- `backend/app/core/bridge.py` 已新增 `bridge_config_to_env_async()` / `reload_bridged_config_async()`；应用启动、系统验证、配置重载接口已切到 async bridge。
- `backend/app/services/sources/manager.py` 构造期不再同步读取 priority；`app/routers/sources.py` 显式 await async priority loader。
- `backend/trader/flows/providers/china/tushare/common.py` 的 async `connect()` 已改为 async token loader；同步 `connect_sync()` 保留原同步 token loader。
- `backend/trader/flows/providers/us/alpha/common.py` 已新增 `get_api_key_async()`；async token/config 读取不再必须进入 sync facade。
- `backend/trader/flows/sources/models.py` 已新增 `get_stock_basic_info_async()`；全量股票列表读取通过 async cursor，原同步方法保留给 CLI/legacy。
- `backend/app/services/analysis/simple/runner.py` 的 progress update 已改为通过运行时 event loop 提交 `_update_progress_async()`；runner 状态更新不再创建新 event loop 或调用 sync DB。
- `backend/app/worker/tushare/sync/models.py` 的 worker progress/status 写入已改为 async DB，并保留取消请求检查。
- `backend/app/services/scheduler/runtime.py` 的 scheduler progress 查询、更新、插入已改为 async DB；`TaskCancelledException` 不再被宽泛异常吞掉。
- `backend/app/core/database.py` 的 `get_postgres_db_sync()` 已标记为 CLI/脚本/legacy 同步边界，async runtime 默认会被 guard 拦截。
- `backend/app/db/store/helpers.py` 已新增 `allow_sync_postgres_in_async(...)` 显式 legacy 放行和 `_run_blocking()` guard；即使 sync DB 已缓存，后续同步桥接调用也不能在 async runtime 中静默阻塞。

### 17.2 已验证

```bash
cd backend && conda run -n trader pytest tests/unit/app/services/analysis/simple/test_provider.py tests/unit/app/services/research/agent/test_stock_async_models.py tests/unit/app/services/research/agent/tool/test_calls.py tests/unit/app/services/research/agent/tool/test_registry.py tests/unit/app/services/research/agent/batch/test_runner.py -q
cd backend && conda run -n trader pytest tests/unit/app/services/analysis/service/test_execute.py
cd backend && conda run -n trader pytest tests/unit/app/services/test_user_async.py tests/unit/app/routers/test_system_async.py tests/integration/app/routers/reports/test_detail_datetime.py tests/integration/app/routers/reports/test_user_isolation.py tests/unit/app/constants/test_capabilities.py tests/unit/app/routers/test_capabilities_async.py tests/unit/app/services/screening/test_service_async.py -q
cd backend && conda run -n trader ruff check app/services/analysis/simple/provider.py app/services/research/agent/stock.py app/services/research/agent/batch/context.py app/services/research/agent/batch/runner.py tests/unit/app/services/analysis/simple/test_provider.py tests/unit/app/services/research/agent/test_stock_async_models.py tests/unit/app/services/research/agent/tool/test_calls.py tests/unit/app/services/research/agent/tool/test_registry.py tests/unit/app/services/research/agent/batch/test_runner.py
cd backend && conda run -n trader ruff check app/services/capability.py app/routers/capabilities.py app/services/screening/service.py app/services/screening/enhanced.py tests/unit/app/constants/test_capabilities.py tests/unit/app/routers/test_capabilities_async.py tests/unit/app/services/screening/test_service_async.py
cd backend && conda run -n trader pyright app/services/capability.py app/routers/capabilities.py app/services/screening/service.py app/services/screening/enhanced.py tests/unit/app/constants/test_capabilities.py tests/unit/app/routers/test_capabilities_async.py tests/unit/app/services/screening/test_service_async.py
cd backend && conda run -n trader pyright app/services/analysis/simple/provider.py app/services/research/agent/stock.py app/services/research/agent/batch/context.py app/services/research/agent/batch/runner.py tests/unit/app/services/analysis/simple/test_provider.py tests/unit/app/services/research/agent/test_stock_async_models.py
cd backend && conda run -n trader pytest tests/unit/app/core/test_unified_async.py tests/unit/app/core/test_bridge_async.py tests/unit/app/routers/test_system_async.py tests/unit/app/routers/config/test_setup_async.py tests/unit/app/services/sources/test_manager_async.py tests/unit/trader/flows/providers/test_tushare.py tests/integration/app/services/sync/test_source.py -q
cd backend && conda run -n trader ruff check app tests tools
cd backend && conda run -n trader pyright
cd backend && conda run -n trader pytest
```

历史结果：

- provider/stock/tool/batch/execute targeted pytest：通过。
- Phase 3 user/system/reports/capability/screening targeted pytest：`17 passed, 2 warnings`；warnings 为既有 `datetime.utcnow()` deprecation。
- 全量 Ruff：通过。
- 全量 Pyright：通过；仅输出现有 venvPath 警告，不是本次代码错误。
- Phase 4 unified/bridge/source-manager/tushare targeted pytest：`20 passed`。
- Phase 4 trader/source 第一批全量 backend pytest：`623 passed, 7 deselected, 2 warnings`；warnings 为既有 `datetime.utcnow()` deprecation。
- 本次 review 纠偏新增验证：
  - `conda run -n trader pytest tests/unit/trader/flows/sources/test_manager_async.py -q`：`9 passed`。
  - `conda run -n trader pytest tests/unit/trader/flows/sources/test_manager_async.py tests/unit/trader/flows/providers/test_alpha.py tests/unit/trader/flows/providers/test_tushare.py -q`：`23 passed`。
  - `conda run -n trader ruff check trader/flows/sources/models.py tests/unit/trader/flows/sources/test_manager_async.py`：通过。
  - `conda run -n trader pyright trader/flows/sources/models.py tests/unit/trader/flows/sources/test_manager_async.py`：`0 errors, 0 warnings, 0 informations`，仅输出既有 venvPath 提示。
  - `conda run -n trader ruff check app tests tools trader`：通过。
  - `conda run -n trader pyright`：`0 errors, 0 warnings, 0 informations`，仅输出既有 venvPath 提示。
  - `conda run -n trader pytest`：`625 passed, 7 deselected, 2 warnings`。
- Phase 5 runner/worker/scheduler targeted 验证：
  - `conda run -n trader pytest tests/unit/app/services/analysis/simple/test_runner_status.py -q`：`1 passed`。
  - `conda run -n trader pytest tests/unit/app/services/analysis/simple/test_runner_status.py tests/unit/app/services/analysis/simple/test_provider.py tests/unit/app/services/analysis/service/test_execute.py -q`：`6 passed`。
  - `conda run -n trader pytest tests/unit/app/worker/tushare/sync/test_models.py -q`：`1 passed`。
  - `conda run -n trader pytest tests/unit/app/services/scheduler/test_runtime.py -q`：`2 passed`。
  - `conda run -n trader pytest tests/unit/app/services/scheduler/test_runtime.py tests/unit/app/services/scheduler/test_gate.py tests/integration/app/services/scheduler/test_init.py tests/integration/app/routers/scheduler/test_nonblocking_market_sync_jobs.py -q`：`7 passed`。
  - `conda run -n trader pytest tests/unit/app/services/analysis/simple/test_runner_status.py tests/unit/app/services/analysis/simple/test_provider.py tests/unit/app/services/analysis/service/test_execute.py tests/unit/app/worker/tushare/sync/test_models.py -q`：`7 passed`。
  - `conda run -n trader ruff check app/services/analysis/simple/base.py app/services/analysis/simple/runner.py app/services/analysis/simple/task.py app/worker/tushare/sync/models.py app/services/scheduler/runtime.py tests/unit/app/services/analysis/simple/test_runner_status.py tests/unit/app/worker/tushare/sync/test_models.py tests/unit/app/services/scheduler/test_runtime.py`：通过。
  - `conda run -n trader pyright app/services/analysis/simple/base.py app/services/analysis/simple/runner.py app/services/analysis/simple/task.py app/worker/tushare/sync/models.py app/services/scheduler/runtime.py tests/unit/app/services/analysis/simple/test_runner_status.py tests/unit/app/worker/tushare/sync/test_models.py tests/unit/app/services/scheduler/test_runtime.py`：`0 errors, 0 warnings, 0 informations`，仅输出既有 venvPath 提示。
- 当前全量 gate：
  - `conda run -n trader ruff check app tests tools trader`：通过。
  - `conda run -n trader pyright`：`0 errors, 0 warnings, 0 informations`，仅输出既有 venvPath 提示。
  - `conda run -n trader pytest`：`647 passed, 3 warnings in 336.92s`，没有 deselected；warnings 为既有/同类 `datetime.utcnow()` deprecation。
- Phase 6.1 sync facade guard 验证：
  - `conda run -n trader pytest tests/unit/app/db/test_sync_guard.py -q`：`4 passed`。
  - `conda run -n trader pytest tests/unit/app/db/test_sync_facade.py tests/unit/app/db/test_sync_guard.py -q`：`7 passed`。
- Phase 6.2 sync facade 连接池影响验证：
  - `conda run -n trader pytest tests/unit/app/core/test_session.py tests/unit/app/db/test_sync_guard.py -q`：`7 passed`。

注意：新增 `tests/unit/trader/flows/sources/test_manager_async.py` 后曾复现 trader flow manager 构造期同步 DB 问题；China/US manager 缺口已修复，并已复跑 full backend gate，见 17.4。

### 17.3 仍需关注的 legacy 边界

- 下列项目不是当前阻塞项，而是必须保留调用方证据和 guard 的 mixed runtime/legacy 边界。后续 review 不能只按函数名搜索判定失败，必须看入口是否 Web/Worker async 主路径。
- `backend/app/services/analysis/service/execute.py` 仍保留线程池同步计算模型，但 Web/Worker async 编排已在线程前预取 DB/provider 配置；Phase 6.1 guard 已覆盖 async runtime 误用，Phase 6.2 已选择通过 guard 阻断长驻 async runtime 误用 sync facade。
- `backend/app/services/analysis/simple/runner.py` 在线程池内仍保留 sync fallback 分支，但 Web/Worker 主路径已传入 `SimpleAnalysisThreadContext`；`backend/app/services/analysis/simple/task.py` 的 async 编排已改为 async 股票名解析。
- `backend/app/services/capability.py` 仍保留同步 legacy 方法；当前 FastAPI capability 主路径已改为 async companion，Phase 6.1 guard 已防止未来 async runtime 静默误用这些同步方法。
- `backend/app/services/screening/service.py` 的 `_get_universe_async()` 已 async 化；`run_async()` 在需要行情/技术字段时已预加载 `trader.flows.sources.get_data_source_manager_async()`，同步 `_run_with_symbols()` 仍保留给 legacy `run()`。
- `backend/app/core/bridge.py`、`backend/app/core/unified.py` 已有 async runtime companion，仍保留 sync legacy 方法；Phase 6.1 guard 已覆盖误用保护。
- `backend/trader/flows/**` 仍是 mixed runtime/legacy 边界，属于 Phase 4，不能机械改 async。Tushare async connect、US Alpha async key loader、China/US manager async availability/priority、async manager cache、`models.py` async stock-list cursor 已处理；剩余同步命中不能只靠 Phase 6.1 guard 解释，必须按调用方证明不是 Web/Worker 主路径。
- `backend/app/services/research/agent/provider/client.py` 和 `backend/app/services/research/agent/stock.py` 中保留的 sync helper 目前仅作为 legacy 同步路径；Phase 6.1 guard 已防止新 async runtime 静默误用。
- `backend/app/services/market/news/write.py` 仍保留 `save_news_data_sync()` 同步兼容方法；当前 worker/router 调用都使用 async `save_news_data()`，Phase 6.1 guard 已防止 async runtime 静默误用 sync 方法。
- Phase 6.2 已选择不新增独立 sync pool 配置；连接池放大风险通过 Phase 6.1 guard 阻断长驻 async runtime 使用 sync facade。

### 17.4 当前 Review 纠偏记录

这次 review 以当前代码为准，发现原有执行记录对 Phase 3.4 和 Phase 4 的完成度描述偏乐观。随后已修复 China/US manager 的构造期同步 DB、async availability/priority loader、async manager cache，并迁移 screening、quotes ingestion、market sync source、stocks fallback 的 Web/Worker 调用方。本次复核又补齐了 US Alpha async key loader 和 `models.py` async stock-list cursor。

代码证据：

- `backend/app/main/application.py`：scheduler 现在注册 `_run_worker_coroutine_job`，并在 wrapper 内 `async with scheduler_gate.heavy_data_sync()` 或 `light_status()` 后 `await worker(...)`；`backend/app/main/setup.py` 的 `asyncio.run()` wrapper 仍保留为 legacy，但不再作为 scheduler 主入口。
- `backend/trader/flows/sources/common.py`：`DataSourceManager.__init__()` 现在只用默认启用集初始化 available sources，不再构造期读取 sync DB；sync priority/config loader 保留为 legacy，async runtime 使用 async companion。
- `backend/trader/flows/sources/provider.py`：`USDataSourceManager.__init__()` 现在不再构造期读取 sync DB；`_get_enabled_sources_from_db()` 和 `_get_datasource_configs_from_db()` 仍是 sync legacy 方法，Phase 6.1 guard 已防止 async runtime 静默误用。
- `backend/trader/flows/providers/us/alpha/common.py`：`get_api_key_async()` 已按数据库配置、环境变量、配置文件优先级读取；同步 `get_api_key()` 保留。
- `backend/trader/flows/sources/models.py`：`get_stock_basic_info_async()` 已新增，全量股票列表走 async cursor；同步 `get_stock_basic_info()` 中的 `list(collection.find(...))` 作为 legacy 保留。
- 当前同步 cursor 剩余命中需要分类处理：`app/core/bridge.py`、`app/services/research/agent/provider/client.py` 属于 sync legacy/compat 路径；`trader/flows/sources/provider.py` 和 `trader/flows/sources/models.py` 属于 trader sync legacy；`app/scripts/keys.py` 属于脚本路径。
- 本次追加 review 曾发现 `backend/app/services/analysis/simple/*` 仍是 Web/Worker 主路径：`SimpleAnalysisService` 由 `backend/app/worker.py` 和 `backend/app/worker/analysis.py` 调用，不能把线程内同步 provider 查询和同步股票名解析继续归类为普通 legacy。该缺口已按 Task 2.6 修复。

测试证据：

```bash
cd backend && conda run -n trader pytest tests/unit/trader/flows/sources/test_manager_async.py -q
```

首次复现结果：

```text
2 failed
- test_china_data_source_manager_constructor_does_not_use_sync_database: DataSourceManager() 仍调用 sync DB 2 次。
- test_china_data_source_manager_async_priority_order: get_data_source_priority_order_async 尚未实现。
```

修复后验证：

```bash
cd backend && conda run -n trader pytest tests/unit/trader/flows/sources/test_manager_async.py -q
cd backend && conda run -n trader pytest tests/unit/trader/flows/sources/test_manager_async.py tests/unit/trader/flows/providers/test_tushare.py tests/unit/trader/flows/data/test_frame.py -q
cd backend && conda run -n trader ruff check trader/flows/sources/common.py trader/flows/sources/provider.py tests/unit/trader/flows/sources/test_manager_async.py
cd backend && conda run -n trader pyright trader/flows/sources/common.py trader/flows/sources/provider.py tests/unit/trader/flows/sources/test_manager_async.py
cd backend && conda run -n trader pytest tests/unit/app/services/screening/test_service_async.py tests/unit/app/services/quotes/test_ingestion_async.py tests/unit/app/services/sync/test_source_async.py tests/unit/app/routers/stocks/test_common_async.py tests/integration/app/services/sync/test_source.py -q
cd backend && conda run -n trader ruff check trader/flows/sources/common.py trader/flows/sources/provider.py trader/flows/sources/cache.py trader/flows/sources/summary.py app/services/screening/service.py app/services/quotes/ingestion.py app/services/sync/source.py app/routers/stocks/common.py tests/unit/trader/flows/sources/test_manager_async.py tests/unit/app/services/screening/test_service_async.py tests/unit/app/services/quotes/test_ingestion_async.py tests/unit/app/services/sync/test_source_async.py tests/unit/app/routers/stocks/test_common_async.py
cd backend && conda run -n trader pyright trader/flows/sources/common.py trader/flows/sources/provider.py trader/flows/sources/cache.py trader/flows/sources/summary.py app/services/screening/service.py app/services/quotes/ingestion.py app/services/sync/source.py app/routers/stocks/common.py tests/unit/trader/flows/sources/test_manager_async.py tests/unit/app/services/screening/test_service_async.py tests/unit/app/services/quotes/test_ingestion_async.py tests/unit/app/services/sync/test_source_async.py tests/unit/app/routers/stocks/test_common_async.py
cd backend && conda run -n trader pytest
cd backend && conda run -n trader ruff check app tests tools trader
cd backend && conda run -n trader pyright
```

当前结果：

```text
8 passed
23 passed
7 passed
9 passed
23 passed
Ruff passed
Pyright 0 errors, 0 warnings, 0 informations（仅输出既有 venvPath 提示）
此前 Phase 4 快照：625 passed, 7 deselected, 2 warnings
Phase 5 复核：629 passed, 7 deselected, 2 warnings
Phase 6 复核曾为：633 passed, 7 deselected, 2 warnings
当前已修正 pytest 默认过滤配置：647 passed, 3 warnings, no deselected
Full Ruff passed
Full Pyright 0 errors, 0 warnings, 0 informations（仅输出既有 venvPath 提示）
```

修正后的结论：

- 当前 spec/plan 的总体方向仍成立：Web/Worker async runtime 迁移到 async DB，CLI/legacy 保留 sync。
- Phase 4 不能只写“为 trader flow 增加 async companion”；必须明确构造期副作用、全局 manager cache、Web/Worker 调用方迁移、以及中间同步 `_run_with_symbols()` 这种隐藏调用链。
- China/US manager 的构造期、async availability/priority、async manager cache、US Alpha async key loader、`models.py` async stock-list cursor 测试已通过；screening、quotes ingestion、market sync source、stocks fallback、research/simple provider stock-name 的 Web/Worker 调用方已迁移。Phase 4.4 剩余同步方法必须继续按调用方证明是 CLI/legacy，而不是只靠 guard 解释。
- Phase 5 的 runner 状态写入、Tushare worker progress、scheduler runtime progress 已按 RED/GREEN 修复；原文再把这些列为待办会误导后续执行。
- 长循环 review 结果显示：Tushare gather 是 batch 内有界并发，未发现全量 symbol 无界 gather；已检查的 worker/market 路径未发现慢外部 API 被包在显式 DB transaction 内。
- Phase 6.1 的 sync facade guard 已按 RED/GREEN 修复：`get_postgres_db_sync()` 与 `_run_blocking()` 在 running event loop 内默认抛错，legacy 同步边界必须显式使用 `allow_sync_postgres_in_async(...)` 或环境变量放行。

### 17.5 Review 结论

当前改造方向符合代码逻辑，但原计划确实漏写了 batch runtime 调用链，低估了“空 payload 提前查 DB”的行为风险，也低估了 trader flow 构造期副作用对 screening/quotes 等 async runtime 的影响。追加 review 又确认了一个核心缺口：`SimpleAnalysisService` 的线程池主路径原先在线程内同步读取 provider 配置，并在 async 编排中同步补股票名；该问题已按 Task 2.6 修复。China/US manager、async manager cache、US Alpha async key loader、`models.py` async stock-list cursor、第一批 Web/Worker 调用方、Phase 5 runner/worker/scheduler progress、Phase 6.1 sync facade guard，以及 Phase 6.2 sync facade 连接池影响策略均已修复。后续 review 的核心不应只看文档格式，而应继续按调用链逐项证明：入口是否 async、配置读取是否 async、是否仍通过 cursor 同步迭代触发 `_run_blocking()`、测试是否锁住业务契约。

### 17.6 本次核心 Review 结论

本次 review 不是文档格式 review，而是按当前代码逻辑重新核对方案是否成立。

结论：方案大方向正确，且本次已按代码逻辑纠偏文档与实现。Task 2.6 已修复 `SimpleAnalysisService` 的主路径缺口；全量 backend gate 和运行时 smoke 已补齐。runtime smoke 期间发现的独立 `market_quotes.legacy_id` dual-write 幂等性 warning 已定位并修复 mapper 根因；backend reload 后通过真实 DB smoke 与日志复核确认未再出现同类 warning。

本次已修改的代码：

- `backend/app/services/analysis/simple/base.py`：`ThreadPoolExecutor(max_workers=3)` 已改为 `settings.ANALYSIS_MAX_WORKERS`，默认 3。
- `backend/app/services/analysis/simple/task.py`：进入线程池前已 await async 模型/provider 上下文解析；`create_analysis_task()` 中股票名补全已改为 async path。
- `backend/app/services/analysis/simple/runner.py`：Web/Worker 主路径已使用 `SimpleAnalysisThreadContext`，线程内不再为 provider 配置读取同步查 DB；错误上下文优先复用 context。
- `backend/app/services/analysis/simple/provider.py`：已新增 `_get_stock_info_safe_async()`；同步 `_get_stock_info_safe()` 保留给 legacy caller。
- `backend/app/core/config.py`、`backend/.env.example`：已新增 `ANALYSIS_MAX_WORKERS=3` 配置入口。
- `backend/app/db/document.py`：`market_quotes` 专用表 legacy id 改为按 `(source, code)` 稳定生成，避免 document-store 自动双写路径使用随机 `_id` 撞上 `uq_market_quotes_legacy_id`。

已经符合方案的代码：

- `backend/app/main/application.py`：scheduler 已使用 coroutine wrapper 和 `SchedulerGate`，不再使用 `backend/app/main/setup.py` 的 `asyncio.run()` wrapper 作为 APScheduler 主入口。
- `backend/app/services/analysis/service/execute.py`：线程池计算模型保留，但 DB/provider 配置已在线程前 async 预取。
- `backend/app/db/store/helpers.py` 与 `backend/app/core/database.py`：sync facade guard 已作为防误用底线存在。

验收门槛：

- 不能只看 `get_postgres_db_sync()` 命中数；还必须检查 `PostgresCursor.__iter__()` 触发的 `list(collection.find(...))` 和同步 `for ... in collection.find(...)`。
- 每个剩余同步命中必须证明调用方是 CLI/脚本/明确 legacy；只写“guard 会拦截”不算完成。
- simple runner targeted tests、Ruff、Pyright 已通过；全量 backend pytest 和运行时 smoke 已补齐。后续新增改动需要按影响范围重跑 targeted/full gate。
- 当前已补充全量 backend gate 和运行时 smoke：
  - Full Ruff：通过。
  - Full Pyright：`0 errors, 0 warnings, 0 informations`，仅输出既有 venvPath 提示。
  - Full pytest：`647 passed, 3 warnings in 336.92s`，没有 deselected。
  - Runtime smoke：`/docs` 200，`/api/health` 200，前端 `/agent?mode=stock` 200；未带登录态的 `/api/config/llm` 返回 401，认证边界正常；登录态 `/api/config/llm` 返回 200。
  - PostgreSQL 连接观测：`trading_agents_cn`，观测瞬间 `active=1`、`idle=3/4`、`idle in transaction=1`。
  - market_quotes 双写 smoke：同一 `code/source` 两次 document-store 写入后专用表保持 1 行，`legacy_id=market_quotes:codex_smoke:CDXSMOKE1`，未再出现 `uq_market_quotes_legacy_id` warning。
