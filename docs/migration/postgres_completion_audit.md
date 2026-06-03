# PostgreSQL Migration Completion Audit

Date: 2026-06-03

This audit maps the migration task plan to current implementation evidence. It is the local implementation completion record; target-environment cutover still requires running the cutover runbook against the target MongoDB/PostgreSQL/service endpoints.

## Gate Summary

| Gate | Status | Evidence |
| --- | --- | --- |
| Inventory and API contract scan | passed locally | `postgres_migration_inventory.py` reports `response_model_dict_endpoints=0`, `raw_dict_request_bodies=0`, and `missing_response_model_endpoints=0`. |
| PostgreSQL dependencies and settings | passed | `backend/pyproject.toml`; `Settings.POSTGRES_URL`; `backend/tests/config/test_settings.py`. |
| SQLAlchemy/Alembic foundation | passed | `backend/app/db/session.py`; `backend/alembic`; offline SQL generation produces 624 lines. |
| ObjectId and JSONB compatibility | passed | `JsonbLegacyMixin`; mapper tests for ObjectId, JSON payload normalization, and stable fallback `legacy_id`. |
| Hot field split and indexes | passed | `backend/app/db/model.py`; `backend/support/db/models/module.py`; query plan checker. |
| Mongo to PostgreSQL migrator | passed | `HOT_COLLECTIONS` covers 35 configured collections; migrator and local seeded migration passed. |
| Worker and scheduled-write dual-write | passed locally | `worker_dual_write_coverage.md` covers 18 worker writes across 9 files; startup sync gate verified locally. |
| PostgreSQL read repositories | passed locally | PG-first repository/service tests and live API smoke cover hot read paths with Mongo fallback. |
| Pydantic router contracts | passed locally | Inventory scan has no `response_model=dict`, no raw dict request bodies, and no missing explicit response models; non-JSON routes use explicit opt-outs. |
| Config/runtime env risk boundary | passed locally | `app.core.runtime_env.apply_runtime_env`; config service dual-write tests; settings tests; OpenAPI/import boundary test. |
| Cutover and rollback tooling | passed locally | consistency, query plan, data-path smoke, API smoke, cutover gate, and runbook exist and passed in isolated services or dry-run. |
| Long-tail write closure | passed locally | `postgres_long_tail_coverage.md` maps remaining dynamic/long-tail writes, inventory `collection=null` audit rows, and explicit Mongo-only export case. |
| Performance preflight | passed locally | query plan checker validates 9 representative high-frequency queries do not filter on JSONB payload. |
| Migration document integrity | passed | `backend/tests/test_migration_docs_integrity.py` verifies migration docs do not reference missing repo files. |
| Default backend regression suite | passed locally | `cd backend && python -m pytest -q` passed with `1291 passed, 31 skipped, 1 deselected, 515 warnings, 64 subtests passed`. |

## Task Evidence

### T0. Migration Inventory And Contract Freeze

Status: passed locally for legacy dict blockers and explicit response model coverage.

Implementation:
- `backend/scripts/postgres/migration/inventory/script.py`
- `docs/migration/postgres_inventory.json`

Evidence:
- Summary contains Mongo access, Mongo writes, worker write files, `response_model=dict`, and raw dict request body counts.
- Latest generated summary:
  - `mongo_access_files=70`
  - `mongo_access_points=252`
- `mongo_write_operations=160`
- `worker_mongo_write_files=9`
- `response_model_dict_endpoints=0`
- `missing_response_model_endpoints=0`
- `raw_dict_request_bodies=0`
- Test: `backend/tests/test_postgres_migration_inventory.py`

### T1. Dependencies And Settings

Status: passed.

Implementation:
- `backend/pyproject.toml` adds `sqlalchemy`, `asyncpg`, `alembic`, and `pydantic-settings`.
- `backend/app/core/config.py` uses `BaseSettings` and exposes PostgreSQL connection settings.

Evidence:
- `Settings.POSTGRES_URL` prefers `DATABASE_URL` and otherwise builds `postgresql+asyncpg://...`.
- Tests cover env/default priority in `backend/tests/config/test_settings.py`.
- Docker Compose and env templates include PostgreSQL connection variables and keep migration switches disabled by default.
- Docker Compose backend migration switches use env interpolation defaults so `deploy/env/postgres-dual-write.env` and `deploy/env/postgres-read.env` can move the service through cutover phases without editing compose YAML.
- Backend Dockerfile installs `backend/pyproject.toml` dependencies through `pip install ./backend`, so PostgreSQL migration libraries are included in Docker images built from this branch.
- Test: `backend/tests/test_postgres_deploy_config.py`.

### T2. SQLAlchemy Session And Alembic Foundation

Status: passed.

Implementation:
- `backend/app/db/session.py`
- `backend/app/db/base.py`
- `backend/alembic.ini`
- `backend/alembic/env.py`
- `backend/alembic/versions/initial.py`

Evidence:
- Session lifecycle tests: `backend/tests/db/test_session.py`, `backend/tests/db/test_database_lifecycle.py`, `backend/tests/db/test_alembic_foundation.py`.
- Offline SQL generation passed:
  - `cd backend && alembic -c alembic.ini upgrade head --sql >/tmp/trading_agents_postgres_offline.sql`
  - `wc -l /tmp/trading_agents_postgres_offline.sql` returned `624`.

### T3. ObjectId Compatibility And JSONB Mapping

Status: passed.

Implementation:
- `backend/app/db/model.py`
- `backend/app/db/document_mapper.py`
- `backend/app/db/postgres_writes.py`

Evidence:
- Every migrated table uses `legacy_id` plus `payload JSONB`.
- `backend/support/db/models/module.py` asserts `legacy_id` and `payload JSONB` across migrated tables.
- `backend/tests/db/test_document_mapper.py` covers ObjectId string conversion, datetime JSON normalization, Decimal handling, and stable fallback `legacy_id`.

### T4. Hot Query Field Splitting

Status: passed.

Implementation:
- Split columns and indexes in `backend/app/db/model.py`.
- PostgreSQL upsert mappers in `backend/app/db/document_mapper.py` and `backend/app/db/postgres_writes.py`.
- Hot-field cutover checklist in `docs/migration/postgres_hot_field_matrix.md`.

Evidence:
- `backend/support/db/models/module.py` asserts split hot fields, uniqueness, and expected indexes.
- Query plan compile check confirms representative filters use columns rather than JSONB payload.
- The cutover runbook references `docs/migration/postgres_hot_field_matrix.md`; document integrity tests verify the reference exists.

### T5. Mongo To PostgreSQL Batch Migrator

Status: passed.

Implementation:
- `backend/app/db/mongo_to_postgres_migrator.py`
- `backend/scripts/postgres/consistency/check/script.py`

Evidence:
- `HOT_COLLECTIONS` covers the configured first-wave collection set, including `quotes_ingestion_status` normalized into `sync_status`.
- `backend/tests/db/test_mongo_to_postgres_migrator.py` covers batch commits and summary output.
- Local seeded migration processed 35 configured collections and consistency passed with `all_consistent=true`.

### T6. Worker And Scheduled Job Dual-Write

Status: passed locally.

Implementation:
- `backend/app/db/dual_write.py`
- Worker changes under `backend/app/worker/`
- Scheduler/status writes under `backend/app/services/scheduler_service.py`
- Runtime stock basics writes under `backend/app/services/basics_sync_service.py` and `backend/app/services/multi_source_basics_sync_service.py`
- Multi-source sync cache clearing under `backend/app/routers/multi_source_sync.py`

Evidence:
- `docs/migration/worker_dual_write_coverage.md` covers 18 worker writes in 9 worker files.
- Tests include `backend/tests/db/test_worker_dual_write.py`, `backend/tests/db/test_scheduler_service_dual_write.py`, `backend/tests/db/test_basics_services_dual_write.py`, and dual-write tests for dynamic business collections.
- Startup stock basic sync is gated by `SYNC_STOCK_BASICS_ENABLED`; local API smoke verified no unexpected seeded Mongo collection growth.
- Quote ingestion runtime writes now dual-write `market_quotes` and `quotes_ingestion_status`; status documents are normalized into `sync_status` for migration and consistency.
- Single-source and multi-source stock basics services now dual-write `stock_basic_info` batches and `sync_status` state updates; multi-source cache clear writes a PostgreSQL `sync_status` cleared marker.

Target cutover requirement:
- Re-run worker gate checks against the target service logs before enabling PostgreSQL read.

### T7. Repository Layer And Business Read Paths

Status: passed locally for first-wave cutover paths.

Implementation:
- Repository modules under `backend/app/db/*_repository.py`.
- PG-first service/router integrations across stock, screening, financial, analysis, user, favorites, tags, paper, operation logs, news, internal messages, and social messages.

Evidence:
- Repository and service read tests under `backend/tests/db/`.
- Local live API smoke passed 27 HTTP checks with `POSTGRES_READ_ENABLED=true` and Mongo fallback available.

### T8. Pydantic Interface Model Replacement

Status: passed locally for explicit response model coverage, request bodies, and raw dict response-model blockers.

Implementation:
- `backend/app/models/api_response.py`
- Router response/request model updates.

- Inventory scan: `response_model_dict_endpoints=0`, `raw_dict_request_bodies=0`, `missing_response_model_endpoints=0`.
- Explicit response model coverage was strengthened by adding response models to health, queue stats, notifications, usage statistics, AKShare init, cache management, financial data, historical data, stock basics sync, scheduler, analysis, database, auth, multi-source sync, config, logs, multi-period sync, operation logs, reports, screening, SSE opt-outs, stock data, stock sync, system config, WebSocket stats, and app-level health/root endpoints.
- Router contract tests include response model tests for config, favorites, internal messages, model capabilities, multi-market, news, paper, social media, stocks, tags, and Tushare init.
- OpenAPI generation succeeds with warning escalation and reports OpenAPI `3.1.0`, 254 paths, and 127 component schemas.
- Tests: `python -m pytest backend/tests/test_router_response_model_coverage.py backend/tests/test_postgres_migration_inventory.py backend/tests/test_openapi_import_boundary.py backend/tests/test_migration_docs_integrity.py -q` passed with `12 passed`.
- Behavior regression slice: `python -m pytest backend/tests/test_config_response_models.py backend/tests/test_postgres_deploy_config.py backend/tests/db/test_analysis_dual_write.py backend/tests/db/test_scheduler_service_dual_write.py backend/tests/db/test_operational_dual_write.py backend/tests/db/test_user_service_dual_write.py -q` passed with `24 passed`.

### T9. Config System Risk Governance

Status: passed locally.

Implementation:
- `backend/app/core/runtime_env.py`
- `backend/app/core/config.py`
- `backend/app/services/config_service.py`
- Config documents mapped to `system_config_documents`.

Evidence:
- Runtime env tests: `backend/tests/config/test_runtime_env.py`.
- Settings tests: `backend/tests/config/test_settings.py`.
- Config dual-write tests: `backend/tests/db/test_config_service_dual_write.py`.
- Provider initialization and normalization scripts now dual-write migrated config collections; tests: `backend/tests/test_init_providers_dual_write.py`, `backend/tests/test_normalize_provider_keys_script.py`.
- Import/schema boundary test: `backend/tests/test_openapi_import_boundary.py` verifies OpenAPI generation does not initialize runtime config storage or attempt unauthenticated Mongo config reads.

Boundary retained:
- DB-backed business config must not override DB connection bootstrapping.
- Historical config bridge behavior remains compatible and should be retired only in a later focused cleanup.

### T10. Cutover, Rollback, And Acceptance Tooling

Status: passed locally; target cutover pending target environment.

Implementation:
- `backend/scripts/postgres/consistency/check/script.py`
- `backend/scripts/postgres/cutover/smoke/script.py`
- `backend/scripts/postgres/api/smoke/script.py`
- `backend/scripts/postgres/cutover/gate/script.py`
- `backend/scripts/postgres/cutover/evidence/check/script.py`
- `backend/scripts/postgres/rollback/check/script.py`
- `backend/scripts/postgres/local/cutover/verify/script.py`
- `backend/scripts/postgres/runtime/log/check/script.py`
- `docs/migration/postgres_cutover_runbook.md`
- `docs/migration/postgres_local_verification.md`

Evidence:
- Local seeded consistency: `all_consistent=true`.
- Local seeded data-path smoke: `all_passed=true`.
- Local live FastAPI API smoke: `all_passed=true`, 27 checks.
- Repeatable local verification script exists for disposable Docker MongoDB/PostgreSQL, representative seed data, Alembic, migrator, and cutover gate orchestration.
- Repeatable local verification script can optionally pass a real backend log through the nested cutover gate with `--runtime-log`, so `gate/summary.json` records the runtime log step; it does not fabricate log evidence when no service log is supplied.
- Repeatable local verification script passes `--target-env local-seeded` and phase-specific `--target-phase` into the nested cutover gate, so local evidence bundles include `gate/00_target_manifest.json` and can be checked with `--require-target-manifest`.
- Cutover gate can include runtime log validation directly with `--runtime-log`, so local and target evidence bundles share the same runtime log shape instead of relying on an out-of-band command.
- Latest local orchestration run passed at `/tmp/trading_agents_postgres_local_cutover_manifest_current` with `all_passed=true`: `alembic_upgrade`, `mongo_to_postgres_migrator`, nested cutover gate, and nested evidence bundle check.
- Nested local cutover gate passed inventory, Alembic offline SQL, consistency over `28` collection groups, query-plan checks over `9` representative queries, and data-path smoke over `13` check groups.
- Nested evidence bundle check enforces `--require-target-manifest --expected-phase pre-read` for local seeded verification.
- Local verifier cleanup now runs even when container startup fails, preventing partial Mongo/PostgreSQL test containers from remaining after a port conflict or Docker startup error.
- Evidence bundle checker validates saved `summary.json`, required output files, step statuses, and semantic JSON fields; it passed against `/tmp/trading_agents_postgres_local_cutover_current/gate`.
- Target evidence bundles can include `00_target_manifest.json`; evidence checks can require it with `--require-target-manifest --expected-phase <phase>` so pre-read, post-read, and rollback evidence cannot be accepted without a target environment label and phase.
- Evidence bundle checker can require `api_smoke.json` to contain a passed `migration_state` check with `--require-api-migration-state`, proving the running service exposes the expected PostgreSQL read/write switches.
- Evidence bundle checker can require `runtime_log_check.json` with `--require-runtime-log-check` and semantically validate runtime log check JSON when the step is included in `summary.json`.
- Evidence bundle checker can validate standalone rollback drill bundles with `--rollback-only --require-rollback-check`; rollback evidence must prove PostgreSQL read is disabled and API smoke passes from Mongo read.
- Cutover gate dry-run generated `summary.json` and a target evidence command list without exposing secrets.
- Cutover gate validates semantic JSON acceptance fields, not just subprocess exit codes: inventory contract counts, consistency `all_consistent`, query-plan `all_required_without_payload_filter`, and smoke `all_passed`.
- Standalone inventory and consistency CLI gates also fail closed by default: inventory exits non-zero on contract regressions; consistency exits non-zero when `all_consistent=false`.
- Runbook contains rollback and stop conditions.
- Runbook includes Docker Compose `exec backend` equivalents for Alembic, migrator, cutover gate, and evidence bundle checks.
- Runbook includes Docker Compose `--env-file .env --env-file deploy/env/postgres-dual-write.env` and `--env-file .env --env-file deploy/env/postgres-read.env` commands for stage changes.
- Runbook references non-secret env templates for target evidence phases: `deploy/env-templates/postgres-pre-read-evidence.env.example`, `deploy/env-templates/postgres-post-read-smoke.env.example`, and `deploy/env-templates/postgres-rollback-smoke.env.example`.
- Runbook includes backend log capture, integrated `postgres_cutover_gate.py --runtime-log`, standalone diagnostic `postgres_runtime_log_check.py`, and evidence checker `--require-runtime-log-check` commands.
- Runbook requires target evidence manifests for pre-read, post-read, and rollback checks using `--require-target-manifest --expected-phase <phase>`.
- Runbook separates pre-read stop conditions from post-read acceptance conditions, so API smoke is required before accepting the cutover, not before enabling PostgreSQL read.
- Test: `backend/tests/test_postgres_local_cutover_verify.py`.
- Test: `backend/tests/test_postgres_cutover_evidence_check.py`.
- Test: `backend/tests/test_postgres_rollback_check.py`.
- Test: `backend/tests/test_postgres_runtime_log_check.py`.
- Test: `backend/tests/test_postgres_deploy_config.py`.

Target cutover requirement:
- Do not claim production cutover until schema, migrator, consistency, query plan, data-path smoke, API smoke, and startup worker checks pass on the target environment.

### T11. Remaining Long-Tail Write Closure

Status: passed locally.

Implementation:
- `docs/migration/postgres_long_tail_coverage.md`
- Additional JSONB-first models and dual-write mappings for notifications, token usage, internal messages, social messages, scheduler extensions, analysis extensions, security/session collections, backups, and news.

Evidence:
- Long-tail coverage file maps each discovered collection to a PostgreSQL target, merged table, or explicit Mongo-only reason; dynamic write audit rows cover every inventory `collection=null` write point and include runtime quote ingestion dual-write.
- Provider initialization and provider-key normalization scripts are no longer Mongo-only for migrated config collections; they dual-write provider/config/catalog replacements and duplicate tombstones.
- The retained backup export path is read-only for arbitrary Mongo collections; no PostgreSQL write is required.

### T12. Pre-Read-Cutover Performance Acceptance

Status: passed locally.

Implementation:
- `backend/app/db/query_plan_checker.py`
- `backend/scripts/postgres/query/plan/check/script.py`
- `docs/migration/postgres_hot_field_matrix.md`

Evidence:
- Compile-only query plan check covers 9 representative queries and reports `all_required_without_payload_filter=true`.
- Local PostgreSQL EXPLAIN check passed in the isolated seeded environment.
- Hot-field matrix maps query-plan gates to required split columns and indexes for stock, quote, historical quote, financial, operation log, user preference, paper trading, worker/status, user/security, news, and dynamic business tables.

Target cutover requirement:
- Re-run with target-size data and save the JSON EXPLAIN output before PostgreSQL primary read.

### T13. Rollback And Runtime Observability

Status: passed locally; target runtime evidence pending.

Implementation:
- `backend/app/db/dual_write.py`
- `backend/scripts/postgres/cutover/gate/script.py`
- `backend/scripts/postgres/consistency/check/script.py`
- `backend/scripts/postgres/migration/inventory/script.py`
- `backend/scripts/postgres/runtime/log/check/script.py`
- `backend/scripts/postgres/rollback/check/script.py`
- `docs/migration/postgres_cutover_runbook.md`

Evidence:
- Four switch states are documented in the runbook: `mongo`, `dual_write`, `postgres_read_mongo_fallback`, and `postgres`.
- Rollback does not require schema rollback: disable `POSTGRES_READ_ENABLED`, keep or disable dual-write based on PostgreSQL write health, restart the service, then re-run consistency.
- Dual-write event logging is centralized in `backend/app/db/dual_write.py`; every successful hot-collection dual-write logs collection, status, attempted/written counts, derived `legacy_ids`, and failure reason at `INFO`, while failures log at `WARNING`.
- `backend/tests/db/test_dual_write.py` covers successful write observability, fail-open failure observability, fail-closed raising, disabled/unsupported skips, batch commit behavior, and Mongo-only warnings.
- `postgres_cutover_gate.py` saves a redacted environment snapshot and validates semantic JSON fields instead of trusting subprocess exit codes alone.
- `postgres_cutover_gate.py --target-env <target-env> --target-phase <phase>` writes non-secret `00_target_manifest.json` only after explicit target preflight passes; `postgres_cutover_evidence_check.py --require-target-manifest --expected-phase <phase>` validates it.
- Target runs can use `--require-explicit-env` to fail before executing gates when MongoDB, PostgreSQL, target label/phase, or API smoke credentials are not explicitly configured; it also blocks phase-shape mistakes such as `post-read` with `--skip-api-smoke` or trying to run rollback through the cutover gate.
- Target runs can pass backend logs to `postgres_cutover_gate.py --runtime-log` and require `runtime_log_check.json` in the evidence bundle; strict runtime log checks fail on missing startup sync-disable evidence, missing successful dual-write events, any dual-write failure, or any Mongo-only migration warning.
- Target rollback drills can save `api_smoke.json`, `consistency.json`, and `rollback_check.json`; `postgres_cutover_evidence_check.py --rollback-only --require-rollback-check` validates the standalone rollback bundle. Rollback API smoke must include the `migration_state` check from `/api/system/config/summary`, proving the running service has `POSTGRES_READ_ENABLED=false`.
- `postgres_rollback_check.py --output-dir --target-env` writes rollback `00_target_manifest.json`, so rollback evidence uses the same manifest validation path as cutover evidence without hand-written JSON; it fails fast with structured JSON when the target environment label is missing.
- `postgres_migration_inventory.py` and `postgres_consistency_check.py` fail closed by default; diagnostic bypass flags are explicit and documented.
- Runbook stop conditions cover missing consistency, Mongo-only worker writes, startup mutation, query-plan payload filters, failed data-path smoke, failed API smoke, and missing fallback evidence.

Target cutover requirement:
- Save target service logs proving startup worker gates and dual-write behavior before accepting PostgreSQL primary read.
- Save target `00_target_manifest.json`, `summary.json`, consistency JSON, query-plan JSON, data-path smoke JSON, and API smoke JSON as deployment evidence.
- Save target rollback drill `00_target_manifest.json` and `rollback_check.json` after a controlled rollback exercise before declaring the migration fully reversible.

## Verified Commands

Latest scoped local gates for migration iteration:

```bash
python backend/scripts/postgres/gate/script.py --scope quick
python backend/scripts/postgres/gate/script.py --scope api-contract
python backend/scripts/postgres/gate/script.py --scope cutover
python backend/scripts/postgres/gate/script.py --scope rollback
python backend/scripts/postgres/gate/script.py --scope docs
python backend/scripts/postgres/gate/script.py --scope db
```

Final local acceptance gate before handoff or target cutover:

```bash
python backend/scripts/postgres/gate/script.py --scope full
```

Additional previously used focused commands:

```bash
python -m py_compile backend/app/main.py backend/app/routers/screening.py backend/app/routers/akshare_init.py backend/app/routers/baostock_init.py backend/app/routers/stock_sync.py backend/app/routers/config.py backend/app/services/analysis_service.py backend/app/services/simple_analysis_service.py backend/app/services/screening_service.py backend/app/worker/financial_data_sync_service.py backend/app/worker/tushare_init_service.py backend/app/worker/akshare_init_service.py backend/app/worker/baostock_init_service.py backend/app/worker/multi_period_sync_service.py backend/app/worker/news_data_sync_service.py backend/app/db/dual_write.py
python -m pytest backend/tests/db backend/tests/config backend/tests/test_postgres_migration_inventory.py backend/tests/test_analysis_time_coercion.py backend/tests/test_openapi_import_boundary.py -q
python -m pytest backend/tests/test_migration_docs_integrity.py -q
python -m pytest backend/tests/test_normalize_provider_keys_script.py backend/tests/test_init_providers_dual_write.py -q
python backend/scripts/postgres/migration/inventory/script.py --output docs/migration/postgres_inventory.json
python backend/scripts/postgres/query/plan/check/script.py --compile-only
cd backend && alembic -c alembic.ini upgrade head --sql >/tmp/trading_agents_postgres_offline.sql
cd backend && python -W error::UserWarning -c 'from app.main import app; app.openapi()'
cd backend && python -m pytest tests/config/test_logging_config.py tests/config/test_logging_json.py tests/db/test_dual_write.py -q
python -m pytest backend/tests/test_postgres_cutover_gate.py -q
python -m pytest backend/tests/test_postgres_cutover_script_exit_gates.py -q
python -m pytest backend/tests/test_postgres_local_cutover_verify.py backend/tests/test_postgres_cutover_gate.py backend/tests/test_postgres_cutover_evidence_check.py backend/tests/test_postgres_runtime_log_check.py backend/tests/test_migration_docs_integrity.py backend/tests/test_postgres_deploy_config.py -q
python -m pytest backend/tests/db/test_postgres_api_smoke.py backend/tests/test_postgres_rollback_check.py backend/tests/test_postgres_cutover_evidence_check.py backend/tests/test_postgres_deploy_config.py backend/tests/test_migration_docs_integrity.py backend/tests/test_postgres_migration_inventory.py -q
python backend/scripts/postgres/cutover/gate/script.py --dry-run --compile-only-query-plan --skip-api-smoke --output-dir /tmp/trading_agents_cutover_gate_dry_run
python backend/scripts/postgres/local/cutover/verify/script.py --output-dir /tmp/trading_agents_postgres_local_cutover_manifest_current --postgres-port 55433
python backend/scripts/postgres/cutover/evidence/check/script.py --require-target-manifest --expected-phase pre-read /tmp/trading_agents_postgres_local_cutover_manifest_current/gate
POSTGRES_READ_ENABLED=false POSTGRES_DUAL_WRITE_ENABLED=true python backend/scripts/postgres/rollback/check/script.py --api-smoke-json <rollback-api-smoke.json> --consistency-json <rollback-consistency.json>
python backend/scripts/postgres/cutover/evidence/check/script.py --rollback-only --require-rollback-check <rollback-evidence-dir>
cd backend && python -m pytest -q
```

Additional local integration evidence is recorded in `docs/migration/postgres_local_verification.md`.

Latest local results:

- Scoped migration test gate real runs:
  - `quick`: `10 passed`
  - `api-contract`: `6 passed`; inventory summary stayed at `response_model_dict_endpoints=0`, `raw_dict_request_bodies=0`, `missing_response_model_endpoints=0`
  - `cutover`: `45 passed`
  - `rollback`: `42 passed`
  - `docs`: `15 passed`
  - `db`: `209 passed, 46 warnings`
- Migration-focused test gate: `246 passed, 46 warnings`.
- Inventory scan: `mongo_access_files=70`, `mongo_access_points=252`, `mongo_write_operations=160`, `worker_mongo_write_files=9`, `response_model_dict_endpoints=0`, `raw_dict_request_bodies=0`, `missing_response_model_endpoints=0`.
- Query plan compile gate: `all_required_without_payload_filter=true` for 9 representative high-frequency queries.
- Alembic offline SQL generation: `624` lines.
- Logging and dual-write observability gate: `13 passed` (`tests/config/test_logging_config.py`, `tests/config/test_logging_json.py`, `tests/db/test_dual_write.py`).
- Migration docs integrity gate: `7 passed`.
- Provider script dual-write gate: `6 passed`.
- Cutover/local evidence gate tests: `45 passed`.
- Standalone cutover script exit-gate tests: `4 passed`.
- Runtime log and evidence-bundle gate tests: included in `45 passed`.
- Target evidence manifest gate tests are included in the `cutover` and `rollback` scoped gates; manifest generation redacts secrets and phase mismatch fails evidence validation.
- Rollback evidence, migration-state API smoke, and post-read evidence-state tests are covered by the `rollback` scoped gate (`42 passed`).
- Scoped migration test gate: `backend/scripts/postgres/gate/script.py` with `--dry-run` and `--list-scopes` passed; `backend/tests/test_postgres_test_gate.py` passed with `5 passed`.
- Post-read evidence CLI smoke: `postgres_cutover_evidence_check.py --require-api-smoke --require-api-migration-state` returned `all_passed=true` on a synthetic bundle containing a passed `migration_state` API check.
- Rollback evidence CLI smoke: `postgres_rollback_check.py` plus `postgres_cutover_evidence_check.py --rollback-only --require-rollback-check` returned `all_passed=true` on a synthetic rollback bundle containing a passed `migration_state` API check.
- Cutover gate dry-run: `all_passed=true`.
- Repeatable local cutover verification: `all_passed=true` at `/tmp/trading_agents_postgres_local_cutover_manifest_current`; nested gate writes `gate/00_target_manifest.json` with `target_env=local-seeded`.
- Evidence bundle verification: `all_passed=true` at `/tmp/trading_agents_postgres_local_cutover_manifest_current/gate`; local evidence can be checked with `--require-target-manifest --expected-phase pre-read`.
- Backend default test suite: `1291 passed, 31 skipped, 1 deselected, 515 warnings, 64 subtests passed`.

## Remaining Completion Conditions

The PostgreSQL data, dual-write, local cutover, and runtime evidence tooling are locally verified, but the full migration objective is not complete yet.

Remaining local condition:
- Target-environment cutover and rollback verification still need to be run against the real MongoDB/PostgreSQL/service endpoints before declaring migration complete.

Remaining target-environment condition:
- A real environment is not cut over by this branch alone. Final target cutover requires an operator to run `docs/migration/postgres_cutover_runbook.md` against the intended environment and retain the generated outputs.
