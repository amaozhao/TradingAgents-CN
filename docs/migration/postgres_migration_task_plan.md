# PostgreSQL 迁移任务规划

## 当前迁移基线

- Mongo 访问面：70 个应用 Python 文件，252 个访问点，160 个写操作。
- 接口契约面：`response_model=dict` 接口已清零，裸 `dict` 请求体已清零；inventory 已新增显式 `response_model` 缺口统计，当前 `missing_response_model_endpoints=0`。普通 JSON endpoint 已补显式 Pydantic 响应模型，文件下载、流式响应等非 JSON endpoint 已用 `response_model=None` 显式豁免。
- 后台写入面：9 个 worker 文件存在 Mongo 写操作，不能放到最后处理。
- 初始 PostgreSQL 策略：JSONB-first 保接口 payload，同时对高频查询字段拆列；worker 状态集合、用户账户、用户偏好集合、纸上交易状态、操作日志、数据库备份元数据、新闻、调度扩展状态和分析扩展状态纳入第一阶段，避免新状态/用户操作/运维日志继续只写 Mongo。
- 当前剩余长尾写入按清单分流：`market_quotes_hk/us`、`stock_basic_info_hk/us` 已归并到现有热点表；`stock_daily_quotes_hk/us` 仅发现为读取映射，主读切换时归并到 `stock_daily_quotes.market`；`stock_news`、`scheduler_history`、`scheduler_metadata`、`analysis_batches`、`analysis_results`、`notifications`、`token_usage`、`internal_messages`、`social_media_messages`、`stock_daily_quotes` 已纳入 PG；`quotes_ingestion_status` 归并到 `sync_status`；`users_collection` 已作为 `users` 静态别名纳入 `user_accounts`；备份导入对已迁移集合做 replay 双写、未知集合显式 Mongo-only；`user_sessions`、`login_attempts` 已按安全/会话 JSONB-first 纳入 PG，当前只发现 cleanup 删除路径，删除前写 tombstone，TTL/审计高频字段拆列。

## T0. 迁移清单和契约冻结

实现功能：
- 生成 Mongo 访问点、Mongo 写操作、worker 写入点、`response_model=dict` 接口清单。
- 迁移前后每批次都复跑清单，用于确认剩余范围和避免遗漏。

边界：
- 只做代码扫描和报告生成，不改变业务行为。
- 清单是迁移控制面，不替代单元/集成测试。

验收标准：
- `docs/migration/postgres_inventory.json` 能生成。
- 报告包含 summary、contracts、mongo_access、mongo_writes、worker_mongo_write_files。
- 报告包含裸 `dict` 请求体统计，用于确认请求体验证已进入 Pydantic 模型入口。
- 扫描脚本有测试覆盖，并能在真实 backend 上运行。

## T1. 依赖和配置系统改造

实现功能：
- 增加 `sqlalchemy`、`asyncpg`、`alembic`。
- 使用 `pydantic-settings` 管理 PostgreSQL 配置。
- 支持 `DATABASE_URL` 优先，缺省时由 `POSTGRES_HOST/PORT/USER/PASSWORD/DB` 组装。
- 保留当前 Mongo/Redis 配置，避免未迁移模块启动失败。

边界：
- 不在此任务切换业务读写。
- 不改现有 HTTP 接口字段。
- `os.environ` 注入只保留当前代理配置行为，后续需集中治理。

验收标准：
- `Settings.POSTGRES_URL` 明确可测。
- `.env`、环境变量和默认值优先级可测。
- 配置测试通过，不影响现有 Mongo/Redis 设置。

## T2. SQLAlchemy 会话和 Alembic 基础

实现功能：
- 新增异步 engine、session factory、FastAPI dependency。
- 新增 SQLAlchemy `Base` 和初始模型。
- 新增 Alembic env、ini、首版 migration。

边界：
- 不自动连接 PostgreSQL，避免本地无 PG 时破坏现有启动。
- 不删除 Mongo 初始化逻辑。

验收标准：
- 未初始化 session 时抛出明确错误。
- `init_postgres/close_postgres` 生命周期可测。
- Alembic offline SQL 可生成。

## T3. ObjectId 兼容和 JSONB 映射

实现功能：
- 所有迁移表都有 `legacy_id`，用于兼容 Mongo ObjectId。
- `payload JSONB` 保留旧文档结构，`_id` 转成字符串。
- 日期、时间、Decimal、ObjectId 可 JSON 化。
- 对无 Mongo `_id` 的新 worker 数据，按业务键生成稳定 `legacy_id`。

边界：
- `legacy_id` 不是对外主键，只用于兼容和追踪。
- 新 PostgreSQL 主键使用 UUID，不模拟 ObjectId。

验收标准：
- ObjectId 转换、payload 保真、业务键 fallback 均有测试。
- 每张迁移表有 `legacy_id` 唯一约束。

## T4. 高频查询字段拆列

实现功能：
- `stock_basic_info` 拆列：`code/source/name/industry/area/market/total_mv/circ_mv/pe/pb/pe_ttm/pb_mrq/updated_at`。
- `market_quotes` 拆列：`code/source/trade_date/open/high/low/close/pre_close/pct_chg/amount/volume/updated_at`。
- `stock_daily_quotes` 拆列：`symbol/code/full_symbol/market/trade_date/period/data_source/open/high/low/close/pre_close/volume/amount/change/pct_chg/deleted/updated_at`，用于历史行情时间序列，不复用只保留最新行情的 `market_quotes` 唯一键。
- `stock_financial_data` 拆列：`code/data_source/report_period/roe/roa/netprofit_margin/gross_margin/updated_at`。
- 分析任务、报告、批次、结果、配置、worker 状态、用户账户、用户偏好、纸上交易、操作日志、备份元数据和新闻先 JSONB-first，保留必要过滤字段。

边界：
- 不在第一批拆所有嵌套字段。
- 不把筛选接口依赖的字段放进纯 JSONB 扫描。

验收标准：
- 模型和 migration 都包含上述字段。
- `industry/total_mv/pe/pb/pct_chg/amount/updated_at/report_period` 有索引；历史行情有 `symbol+trade_date`、`trade_date`、`market+data_source` 索引。
- 业务唯一键有约束：`code+source`、`symbol+trade_date+data_source+period`、`code+data_source+report_period`。
- `docs/migration/postgres_hot_field_matrix.md` 明确列出主读切换前必须保留拆列的高频字段、索引/唯一约束和对应查询计划门禁。

## T5. Mongo 到 PostgreSQL 批量迁移器

实现功能：
- 从 Mongo 读取热点集合。
- 使用 mapper 拆列并保留 payload。
- 使用 PostgreSQL `ON CONFLICT` upsert。
- 按 batch commit，输出每个集合迁移数量和 commit 次数。
- 第一批迁移集合包含 `stock_basic_info`、`market_quotes`、`stock_daily_quotes`、`stock_financial_data`、`stock_news`、`analysis_tasks`、`analysis_reports`、`analysis_batches`、`analysis_results`、`sync_status`、`quotes_ingestion_status`、`scheduler_executions`、`scheduler_history`、`scheduler_metadata`、`users`、`users_collection`、`user_sessions`、`login_attempts`、`user_favorites`、`user_tags`、`paper_accounts`、`paper_positions`、`paper_orders`、`paper_trades`、`operation_logs`、`database_backups`、`notifications`、`token_usage`、`internal_messages`、`social_media_messages`，以及配置集合 `system_configs`、`llm_providers`、`model_catalog`、`market_categories`、`datasource_groupings`。

边界：
- 第一阶段只迁移热点集合和核心分析任务/报告集合，不迁移所有长尾集合。
- 不做 destructive cutover，不删除 Mongo 数据。

验收标准：
- fake Mongo/fake session 测试覆盖 batch commit 和 summary。
- upsert SQL 可编译并包含 `ON CONFLICT`。
- 迁移器可重复执行。

## T6. Worker 和定时任务双写

实现功能：
- 优先处理 9 个 worker 写入文件。
- worker 继续完成原 Mongo 写入，同时写 PostgreSQL 热点表。
- 非 worker 的同步入口同样纳入双写：单源/多源 stock basics 服务的 `stock_basic_info` 批量写入、`sync_status` 状态写入，以及多源同步清缓存的状态清理标记。
- 对失败策略做 fail-open/fail-closed 区分：行情/基础数据同步 PG 写失败可记录并重试；用户交易、账户、任务状态类写失败必须阻断或告警。

边界：
- 不在 worker 双写稳定前切读。
- 不把 worker 留到最后处理，避免新数据继续只进入 Mongo。

验收标准：
- 每个 worker 写入点都有对应 PG upsert；状态集合不得再作为 Mongo-only 豁免。
- 同步服务和同步路由的热点写入有对应 PG upsert 或 tombstone/cleared 状态记录。
- 双写失败有日志、计数和可重试路径。
- 清单中 worker Mongo write files 逐批下降或标记为已双写。
- `docs/migration/worker_dual_write_coverage.md` 覆盖每个 worker 写入点；`sync_status` 和 `scheduler_executions` 必须进入 PG 双写和一致性校验。

## T7. Repository 层和业务读路径迁移

实现功能：
- 为热点集合建立 PostgreSQL repository。
- 筛选、行情、基础信息、财务数据接口切到 repository。
- JSONB payload 用于保持原接口字段结构，拆列用于过滤、排序、分页。
- 用户收藏和标签已具备 PG 双写与迁移基础；主读切换前需要补 repository 读路径或保持 Mongo fallback。
- 纸上交易账户、持仓、订单、成交已具备 PG 双写与迁移基础；reset 操作必须先写 tombstone 再删除 Mongo，避免 PG 残留有效旧状态。
- 用户账户 `users` 已具备 PG 双写与迁移基础；认证主读切换前需要补 repository 读路径或保持 Mongo fallback。
- 操作日志 `operation_logs` 已具备 PG 双写与 tombstone 基础；主读切换前需要补按 `user_id/timestamp/action_type/success` 的 repository 查询，避免日志页在 JSONB 上做高频筛选。
- 数据库备份元数据 `database_backups` 已具备 PG 双写与 tombstone 基础；备份文件本体仍由文件系统/Mongo dump 管理，PG 只承载元数据和删除状态。
- 新闻 `stock_news` 已具备 PG 双写与清理 tombstone 基础；主读切换前需要补按 `symbol/publish_time/data_source/category/sentiment/importance` 的 repository 查询。
- 历史行情 `stock_daily_quotes` 已具备 PG 双写与迁移基础；主读切换前需要补按 `symbol/date range/data_source/period` 的 repository 查询，不能落到 `market_quotes` 最新行情表。
- `stock_daily_quotes_hk/us` 在当前代码中只作为 `UnifiedStockService.get_daily_quotes` 的读取集合名出现；主读切换时应改为统一历史行情 repository 加 `market` 条件，而不是新建 per-market 历史行情表。
- 通知、token 用量、内部消息、社媒消息已具备 PG 双写与迁移基础；主读切换前分别补 `user/status/type`、`provider/model/timestamp/session`、`symbol/type/category/access/importance`、`symbol/platform/type/sentiment/importance` 查询。
- 调度扩展集合 `scheduler_history`、`scheduler_metadata` 已具备 PG 双写与迁移基础；`scheduler_executions` 的 running 插入和 success/failed 更新都必须双写。
- 分析扩展集合 `analysis_batches`、`analysis_results` 已具备 PG 迁移基础；分析清理必须对 `analysis_tasks` 和 `analysis_results` 写 tombstone。

边界：
- 不直接在 router 中写 SQLAlchemy 查询。
- 不一次性迁移所有长尾服务。

验收标准：
- 关键接口响应结构不变。
- 高频查询使用拆列过滤和索引字段。
- Mongo fallback 有开关和审计日志。
- 当前进展：`StockDataService` 的基础信息/实时行情/股票列表、筛选服务、财务数据、`UnifiedStockService.get_daily_quotes`、操作日志列表/统计/CSV 导出、认证用户主读、用户列表、用户自选股列表、用户标签列表、纸上交易账户/持仓/订单只读入口、分析任务状态/结果详情/用户历史、新闻查询、内部消息查询/搜索/统计、社媒消息查询/搜索/统计已具备 PG-first + Mongo fallback。

## T8. Pydantic 接口模型替换

当前状态：
- 已完成本地显式契约收口：`response_model_dict_endpoints=0`、`raw_dict_request_bodies=0`、`missing_response_model_endpoints=0`。
- 已覆盖普通 JSON endpoint 的显式 Pydantic 响应模型；`FileResponse`、`StreamingResponse`、SSE 等非 JSON 响应通过 `response_model=None` 显式标注。
- Router coverage 测试已纳入已完成模块，OpenAPI 可生成。

实现功能：
- 将 `response_model=dict` 分批替换为 Pydantic 模型。
- 请求体验证统一使用 Pydantic 模型，不在 router 内手写字典校验。
- 对兼容字段使用 alias/extra 策略，避免破坏旧前端。

边界：
- 不因模型化删除现有响应字段。
- 不用 `Any` 大面积掩盖真实结构，只有 JSONB payload 兼容区允许。

验收标准：
- `response_model=dict` 清单逐批下降。
- 裸 `dict` 请求体清单为 0。
- 缺失显式 `response_model` 的普通 JSON endpoint 为 0；文件下载、流式响应、WebSocket 等非 JSON 端点必须显式豁免或用 `response_model=None` 标注。
- 每批接口有 contract test 或现有接口测试。
- OpenAPI 可生成且无模型冲突。

## T9. 配置系统风险治理

实现功能：
- 梳理 DB 配置、env 配置、运行时 `os.environ` 注入三类来源。
- 将业务配置读取统一到 Pydantic Settings 或 repository。
- 对代理环境变量注入保留兼容，但隔离到明确函数。
- 新增 `app.core.runtime_env.apply_runtime_env` 作为运行时环境变量写入边界，先承接启动期代理注入。
- 配置集合 `system_configs`、`llm_providers`、`model_catalog`、`market_categories`、`datasource_groupings` 进入 `system_config_documents` JSONB 表；`ConfigService` 主要 CRUD 写路径同步写 PostgreSQL。
- 配置操作脚本也进入迁移边界：`init_providers.py` 和 `normalize_provider_keys.py` 必须对已迁移配置集合写 PostgreSQL upsert/tombstone，不能在切换期继续制造 Mongo-only 配置变更。

边界：
- 不在数据迁移过程中同时重写全部配置桥接逻辑。
- 不允许 DB 配置覆盖启动所需的 DB 连接配置。
- `config_bridge.py` 的历史运行时桥接逻辑保留，后续按配置项逐段迁移到统一 helper，避免一次性重写破坏 TradingAgents 核心库读取行为。
- 删除类配置操作以 tombstone payload 记录到 PostgreSQL，避免 PG 保留无法追踪的旧配置状态；真正的物理删除留到切换后统一处理。

验收标准：
- 启动配置来源可打印、可测试。
- `CONFIG_SOT` 的 file/db/hybrid 行为有测试。
- 无循环依赖：连接 DB 不依赖从 DB 读取的配置。
- 运行时 `os.environ` 写入有 helper 测试覆盖，空值跳过、可选择保留既有 env 值。
- 配置集合 mapper/upsert 和 ConfigService 双写路径有测试覆盖。
- Provider 初始化和归一化脚本的替换、插入、重复项删除有双写测试覆盖。

## T10. 切换、回滚和验收

实现功能：
- 分阶段开关：`mongo`、`dual_write`、`postgres_read_mongo_fallback`、`postgres`。
- 切换前后运行数据一致性校验。
- 保留回滚到 Mongo read 的开关，直到核心接口稳定。
- 提供 `backend/scripts/postgres_consistency_check.py`，比较热点集合 Mongo/PostgreSQL 总数与抽样业务键差异。
- 提供 `backend/scripts/postgres_cutover_gate.py`，编排 inventory、Alembic offline SQL、一致性、查询计划、数据路径 smoke、API smoke、可选 runtime log check，并保存带 `00_target_manifest.json` 的目标环境证据包。
- `postgres_cutover_evidence_check.py --require-api-migration-state` 可强制 post-read API smoke 证据包含 `/api/system/config/summary` 的 `migration_state` 运行态开关校验，避免只凭 HTTP 成功误判切读状态。
- 提供 `backend/scripts/postgres_rollback_check.py`，验证 rollback 演练证据：`POSTGRES_READ_ENABLED=false`、API smoke 通过、API smoke 包含 `/api/system/config/summary` 的 `migration_state` 运行态开关校验、回滚后一致性结果已保存；`postgres_cutover_evidence_check.py --rollback-only --require-rollback-check` 可验证独立 rollback evidence bundle。
- 一致性校验覆盖行情/基础/财务热点表和历史行情表，以及 `stock_news`、`analysis_tasks`、`analysis_reports`、`analysis_batches`、`analysis_results`、`sync_status`/`quotes_ingestion_status` alias、`scheduler_executions`、`scheduler_history`、`scheduler_metadata`、`users`/`users_collection` alias、`user_sessions`、`login_attempts`、`user_favorites`、`user_tags`、`paper_accounts`、`paper_positions`、`paper_orders`、`paper_trades`、`operation_logs`、`database_backups`、`notifications`、`token_usage`、`internal_messages`、`social_media_messages`。
- 当前本地验证：`docs/migration/postgres_local_verification.md` 记录了隔离 Docker Mongo/PostgreSQL 上的 schema、迁移器、一致性检查和 EXPLAIN 采样；目标环境切换前必须复跑同一组命令。

边界：
- 不做无回滚的一次性切换。
- 不在未完成 worker 双写和热点读路径前关闭 Mongo。

验收标准：
- 迁移器重复执行无重复数据。
- `python backend/scripts/postgres_consistency_check.py --sample-limit 500` 输出 `all_consistent=true` 后才允许切 PostgreSQL 主读。
- `postgres_consistency_check.py` 默认在 `all_consistent=false` 时退出非零；只允许诊断场景使用 `--allow-inconsistent`。
- `python backend/scripts/postgres_cutover_gate.py --dry-run --compile-only-query-plan --skip-api-smoke` 可在无目标环境时生成 dry-run 证据摘要；真实目标环境运行不带 dry-run，并通过 `--runtime-log` 把 backend 日志纳入 `summary.json` 和证据包。
- target evidence bundle 必须包含 `00_target_manifest.json`，记录非敏感的目标环境标签和阶段；pre-read/post-read/rollback 验收必须使用 `--require-target-manifest --expected-phase <phase>`。
- post-read evidence bundle 必须用 `--require-target-manifest --expected-phase post-read --require-api-smoke --require-api-migration-state` 校验，证明服务真实处于 PostgreSQL-read 状态。
- rollback 演练必须保存 `rollback_check.json` 并通过 `python backend/scripts/postgres_cutover_evidence_check.py --rollback-only --require-target-manifest --expected-phase rollback --require-rollback-check <rollback-evidence-dir>`；rollback API smoke 必须用 `TRADINGAGENTS_EXPECT_POSTGRES_READ_ENABLED=false` 证明服务实际运行在 Mongo-read 状态。
- 核心接口 contract test 通过。
- worker 不再产生只存在于 Mongo 的新热点数据。
- PostgreSQL 索引命中可以通过 explain 或查询计划抽样确认。
- 本地隔离环境已验证 seeded hot collections `all_consistent=true`；生产或目标环境未验证前不得视为最终 cutover 完成。

## T11. 剩余长尾写入闭环

实现功能：
- 将 inventory 中仍出现的 Mongo 写入按业务风险分流：
  - 行情扩展：`market_quotes_hk`、`market_quotes_us`、`stock_basic_info_hk`、`stock_basic_info_us`、`stock_news`。
  - 调度/同步扩展：`quotes_ingestion_status`、`scheduler_history`、`scheduler_metadata`。
  - 分析扩展：`analysis_batches`、`analysis_results`。
  - 动态业务集合：`notifications`、`token_usage`、`internal_messages`、`social_media_messages`。
  - 历史行情：`stock_daily_quotes`。
  - 历史行情读取别名：`stock_daily_quotes_hk`、`stock_daily_quotes_us` 归并到 `stock_daily_quotes.market`。
  - 备份导入：已迁移集合 replay 到 PG，未知集合 Mongo-only 并记录原因。
  - 安全/会话：`user_sessions`、`login_attempts` 已纳入 PG，保留 payload，拆列 `session_id/user_id/username/ip/expires_at/timestamp/success`，cleanup 删除写 tombstone。
  - 动态写入：无法静态识别的 `None` 集合；当前 `collection` 误名已由 inventory 扫描器解析为真实集合；`users_collection` 已作为静态 alias 归并到 `user_accounts`。
  - 配置脚本：`init_providers.py` 和 `normalize_provider_keys.py` 写入 `llm_providers`、`system_configs`、`model_catalog` 时必须双写到 `system_config_documents`。
- 对每类集合明确处理策略：纳入 PG 表、归并到已有表、只写 tombstone、或保留 Mongo-only 并写明原因。
- 对动态集合写入补人工审计清单，逐个映射到真实集合名，避免扫描器无法识别导致遗漏。

边界：
- 不把所有低频集合强行一次性关系化；接口结构仍以 JSONB-first 保持兼容。
- `user_sessions` 和 `login_attempts` 当前仅发现 cleanup 删除路径；PG 采用 JSONB-first 保留兼容 payload，仅拆 TTL 和审计筛选字段，不新增认证写入行为。
- 对 `_hk/_us` 行情集合，优先评估是否合并到 `stock_basic_info`/`market_quotes` 的 `source/market` 拆列，而不是创建重复表。

验收标准：
- `docs/migration/postgres_inventory.json` 中每个剩余 collection 都能在任务文档或覆盖文档中找到处置结论。
- 动态集合写入没有“未知用途”项；无法迁移的项有明确 Mongo-only 豁免原因和回访任务；`docs/migration/postgres_long_tail_coverage.md` 的 Dynamic Write Audit 必须覆盖 inventory 中每个 `collection=null` 写点。
- 新纳入 PG 的集合具备 schema、mapper、upsert、migration、迁移器、一致性检查、双写测试。

## T12. 主读切换前性能验收

实现功能：
- 对已拆列字段建立 representative 查询用例：股票筛选、行情分页、财务筛选、操作日志按时间/用户/动作筛选、用户偏好查询、纸上交易持仓/订单查询。
- 使用 PostgreSQL `EXPLAIN` 或本地 SQL 编译检查确认过滤条件走拆列字段，不依赖 JSONB 全表扫描。
- 对 JSONB payload 只做响应结构还原和低频兼容查询。
- 提供 `backend/scripts/postgres_query_plan_check.py`：真实 PostgreSQL 环境执行 `EXPLAIN (FORMAT JSON)`；无 PG 时可用 `--compile-only` 生成待执行计划 SQL。

边界：
- 不要求在迁移第一阶段完成所有复杂报表关系化。
- 不用单元测试伪造性能结论；性能验收需要真实或代表性数据。

验收标准：
- 每个主读接口有对应 repository 测试和 contract test。
- 高频查询过滤字段在 SQL 中来自拆列字段。
- 切换前记录查询计划样本，发现 JSONB 全表扫描必须补列或补索引。
- `python backend/scripts/postgres_query_plan_check.py --compile-only` 能通过静态门禁；真实环境必须运行不带 `--compile-only` 的 EXPLAIN 采样。
- `docs/migration/postgres_hot_field_matrix.md` 与查询计划脚本保持一致，作为 runbook 的 worker/status 和热点字段验收入口。

## T13. 回滚和运行期观测

实现功能：
- 每个双写入口记录 collection、legacy_id、状态、失败原因。
- 为迁移器和一致性检查提供可重复运行命令。
- 保留 `mongo`、`dual_write`、`postgres_read_mongo_fallback`、`postgres` 四态开关，并为每态定义允许的读写行为。
- 提供 `docs/migration/postgres_cutover_runbook.md`，覆盖 preflight、schema、迁移、双写、校验、EXPLAIN、切读、回滚和观测证据。
- 提供 `backend/scripts/postgres_cutover_gate.py`，降低目标环境漏跑门禁或漏保存证据的风险；目标环境可用 `--runtime-log` 把运行期日志校验纳入同一个 gate summary。
- 提供 `backend/scripts/postgres_runtime_log_check.py`，对目标 backend 日志中的启动 worker gate、双写成功事件、双写失败和 Mongo-only 警告做机器校验。
- 提供 `backend/scripts/postgres_rollback_check.py`，对 rollback 演练的 Mongo 主读开关、API smoke、一致性证据做机器校验。

边界：
- 不在一致性未通过时关闭 Mongo read fallback。
- 不把 PG 双写失败吞掉为无日志异常；业务安全相关写入必须升级为告警或阻断。

验收标准：
- 双写失败可在日志中定位到集合和业务键。
- 回滚到 Mongo 主读不需要 schema 回滚。
- 切换 runbook 包含迁移、校验、切读、回滚、恢复双写重放步骤。
- cutover gate dry-run 和单元测试通过，且环境快照不输出密码/token 明文。
- runtime log check 严格模式通过，且 evidence checker 在 `--require-runtime-log-check` 下能强制要求 `runtime_log_check.json`。
- target evidence manifest 通过 `--require-target-manifest --expected-phase <phase>` 校验，避免无法追溯证据包属于哪个目标环境和切换阶段。
- `postgres_cutover_gate.py --require-explicit-env` 在目标环境必须提前校验 MongoDB、PostgreSQL、目标环境标签、cutover 阶段和 API smoke 期望开关，缺失时不得继续执行下游门禁。
- `postgres_cutover_gate.py --require-explicit-env` 必须校验阶段形状：`pre-read` 必须跳过 API smoke，`post-read` 必须包含 API smoke，`rollback` 必须使用 `postgres_rollback_check.py` 而不是 cutover gate。
- rollback 阶段的 `00_target_manifest.json` 必须由 `postgres_rollback_check.py --output-dir --target-env` 生成，避免手写 JSON 造成阶段、时间或目标环境标签错误；缺少目标环境标签时必须 fail fast 并输出结构化失败 JSON。
- rollback drill 通过 `postgres_rollback_check.py`，且 evidence checker 在 `--rollback-only --require-target-manifest --expected-phase rollback --require-rollback-check` 下能强制要求 `rollback_check.json`；`api_smoke.json` 必须包含通过的 `migration_state` 检查。
- inventory 和 consistency 单脚本默认 fail closed，避免逐条执行 runbook 时只看 stdout 而漏掉 stop condition。
- `backend/scripts/postgres_test_gate.py` 提供 `quick`、`api-contract`、`cutover`、`rollback`、`db`、`docs`、`full` 分层门禁；迁移迭代默认按修改范围运行小门禁，只有最终本地验收或目标环境 cutover 前才运行 `full`，避免每次小改都触发耗时全量测试。
