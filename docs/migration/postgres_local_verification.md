# PostgreSQL Local Verification Evidence

Date: 2026-06-03

## Environment

Isolated local Docker containers were used, not the developer's existing MongoDB/PostgreSQL services.

| Service | Container | Port | Database |
| --- | --- | ---: | --- |
| MongoDB | `ta_mongo_migration_test` | `27019` | `trading_agents_cn` |
| PostgreSQL | `ta_pg_migration_test` | `55432` | `trading_agents_cn` |
| Redis | `ta_redis_migration_test` | `56379` | n/a |

The MongoDB test database was seeded with one representative document for each configured migration collection.
The FastAPI service was started against the same isolated services with `POSTGRES_DUAL_WRITE_ENABLED=true`, `POSTGRES_READ_ENABLED=true`, and external bulk stock sync disabled.

## Commands

Repeatable local orchestration:

```bash
python backend/scripts/postgres/local/cutover/verify/script.py \
  --output-dir /tmp/trading_agents_postgres_local_cutover
```

The script starts isolated Docker MongoDB/PostgreSQL containers, seeds representative
documents for every configured hot collection, applies Alembic, runs the migrator,
and then runs the cutover gate without API smoke. Add `--api-base-url` and
`--api-token` to include API smoke against an already-running local service.
The nested cutover gate writes `gate/00_target_manifest.json` with
`target_env=local-seeded`; the phase is `pre-read` when API smoke is skipped and
`post-read` when API smoke is included.
The script then runs `postgres_cutover_evidence_check.py` against the nested
gate bundle, so local orchestration fails if the manifest or semantic evidence
checks are missing.

Validate the saved local evidence bundle with the same manifest requirement used
for target environments:

```bash
python backend/scripts/postgres/cutover/evidence/check/script.py \
  --require-target-manifest \
  --expected-phase pre-read \
  /tmp/trading_agents_postgres_local_cutover/gate
```

Schema:

```bash
cd backend
alembic -c alembic.ini upgrade head
```

Migration:

```bash
MONGODB_HOST=localhost \
MONGODB_PORT=27019 \
MONGODB_DATABASE=trading_agents_cn \
MONGODB_DATABASE_SCOPE=explicit \
POSTGRES_HOST=localhost \
POSTGRES_PORT=55432 \
POSTGRES_USER=postgres \
POSTGRES_PASSWORD=postgres \
POSTGRES_DB=trading_agents_cn \
python -m app.db.mongo_to_postgres_migrator --batch-size 5
```

Consistency:

```bash
MONGODB_HOST=localhost \
MONGODB_PORT=27019 \
MONGODB_DATABASE=trading_agents_cn \
MONGODB_DATABASE_SCOPE=explicit \
POSTGRES_HOST=localhost \
POSTGRES_PORT=55432 \
POSTGRES_USER=postgres \
POSTGRES_PASSWORD=postgres \
POSTGRES_DB=trading_agents_cn \
python backend/scripts/postgres/consistency/check/script.py --sample-limit 500
```

Query plans:

```bash
POSTGRES_HOST=localhost \
POSTGRES_PORT=55432 \
POSTGRES_USER=postgres \
POSTGRES_PASSWORD=postgres \
POSTGRES_DB=trading_agents_cn \
python backend/scripts/postgres/query/plan/check/script.py
```

Data-path smoke:

```bash
POSTGRES_HOST=localhost \
POSTGRES_PORT=55432 \
POSTGRES_USER=postgres \
POSTGRES_PASSWORD=postgres \
POSTGRES_DB=trading_agents_cn \
python backend/scripts/postgres/cutover/smoke/script.py --pretty
```

API smoke:

```bash
TRADING_AGENTS_API_BASE_URL=http://127.0.0.1:18080 \
TRADING_AGENTS_API_TOKEN=<smoke-jwt> \
TRADING_AGENTS_SMOKE_STOCK_CODE=000001 \
TRADING_AGENTS_SMOKE_SYMBOL=000001 \
TRADING_AGENTS_SMOKE_SEARCH_QUERY=000001 \
TRADING_AGENTS_SMOKE_TASK_ID=task-1 \
python backend/scripts/postgres/api/smoke/script.py --pretty
```

## Results

Repeatable local orchestration summary:

- Command: `python backend/scripts/postgres/local/cutover/verify/script.py --output-dir /tmp/trading_agents_postgres_local_cutover_manifest_current --postgres-port 55433`
- Result: `all_passed=true`
- Steps passed: `alembic_upgrade`, `mongo_to_postgres_migrator`, `cutover_gate`, `evidence_bundle_check`
- Nested cutover gate passed: inventory, Alembic offline SQL, consistency, query plan, and data-path smoke.
- Nested evidence bundle check passed with `--require-target-manifest --expected-phase pre-read`.
- Output bundle: `/tmp/trading_agents_postgres_local_cutover_manifest_current`
- Target manifest: `/tmp/trading_agents_postgres_local_cutover_manifest_current/gate/00_target_manifest.json`
- The script cleaned up disposable local containers after completion.

Migration summary:

- Migrator processed `34` configured collections.
- Non-empty migrated collections: `analysis_batches`, `analysis_reports`, `analysis_results`, `analysis_tasks`, `database_backups`, `datasource_groupings`, `internal_messages`, `llm_providers`, `login_attempts`, `market_categories`, `market_quotes`, `model_catalog`, `notifications`, `operation_logs`, `paper_accounts`, `paper_orders`, `paper_positions`, `paper_trades`, `quotes_ingestion_status`, `scheduler_executions`, `scheduler_history`, `scheduler_metadata`, `social_media_messages`, `stock_basic_info`, `stock_daily_quotes`, `stock_financial_data`, `stock_news`, `sync_status`, `system_configs`, `token_usage`, `user_favorites`, `user_sessions`, `user_tags`, `users`.
- `users_collection` was covered by the migration configuration but empty in the seed set.

Consistency summary:

- `all_consistent=true`
- Consistency-checked collections: `28`
- Inconsistent collections: none
- `users` consistency merges Mongo sources `users` and `users_collection` before comparing with PostgreSQL `user_accounts`.

Query-plan summary:

- `all_required_without_payload_filter=true`
- Representative queries checked: `9`
- Queries: `stock_screening`, `stock_list_page`, `daily_quotes_range`, `financial_data`, `operation_logs_page`, `user_favorites`, `user_tags`, `paper_positions`, `paper_orders`

Data-path smoke summary:

- `all_passed=true`
- Checks passed: `stock_basic_info`, `stock_list`, `market_quote`, `daily_quotes`, `financial_data`, `analysis_task_report`, `user_preferences`, `paper_trading`, `operation_logs`, `stock_news`, `messages`, `security_sessions`, `system_configs`

Deployment API smoke:

- Script: `backend/scripts/postgres/api/smoke/script.py`
- Scope: local live FastAPI service after `POSTGRES_DUAL_WRITE_ENABLED=true` and `POSTGRES_READ_ENABLED=true`
- Result: `all_passed=true`
- Checks passed: `27`
- Endpoint groups covered: health/ready, public financial and message endpoints, model capabilities, `/api/auth/me`, stock quote/fundamentals/search/info/daily, favorites, tags, paper account, operation logs, news, config, analysis task status/result.

Startup worker guard:

- The local service was started with `SYNC_STOCK_BASICS_ENABLED=false`.
- Startup log confirmed stock basic information sync was disabled.
- MongoDB collection counts after startup and API smoke remained bounded to seeded smoke data: `stock_basic_info=1`, `market_quotes=1`, `operation_logs=1`.
- The verification exposed and fixed a startup risk: `run_sync_with_sources()` was previously scheduled unconditionally and could continue writing fresh stock basics into MongoDB even when the sync flag was disabled.

## Notes

- The first migration attempt exposed an operational issue: offline migration/consistency tools were using full app database initialization and failed when Redis required authentication. The tools now initialize only MongoDB plus PostgreSQL.
- The API smoke exposed two PostgreSQL-read compatibility gaps that were fixed before this evidence was recorded: stock search now reads split PostgreSQL columns before Mongo fallback, and analysis task status now accepts ISO datetime strings returned from JSON payloads.
- This is local seeded-data verification. Production cutover still requires running the same schema, migration, consistency, query-plan, data-path smoke, API smoke, and startup worker checks against the target environment and saving the resulting JSON outputs.
