# PostgreSQL Cutover Runbook

## Scope

This runbook covers the first PostgreSQL cutover for the JSONB-first migration. It does not authorize removing MongoDB data or disabling MongoDB writes. Mongo remains the rollback source until consistency, query-plan, and application checks pass in the target environment.

## Switch States

| State | `POSTGRES_DUAL_WRITE_ENABLED` | `POSTGRES_READ_ENABLED` | Purpose |
| --- | --- | --- | --- |
| `mongo` | `false` | `false` | Baseline Mongo-only behavior. |
| `dual_write` | `true` | `false` | Mongo remains primary read/write; supported writes replay to PostgreSQL. |
| `postgres_read_mongo_fallback` | `true` | `true` | Read supported hot paths from PostgreSQL first; fallback to Mongo on empty/error. |
| `postgres` | `true` | `true` | PostgreSQL primary-read operating mode. Mongo fallback code remains available; do not disable before a separate removal plan. |

Production should set `POSTGRES_DUAL_WRITE_FAIL_OPEN=false` for user/account/trading/task-state writers after PostgreSQL availability is proven. Market-data ingest may remain fail-open during early soak if replay is operationally accepted.

## Preflight

Run from the repository root unless noted.

Docker Compose deployments include a `postgres` service and backend `POSTGRES_*`
environment variables in `deploy/docker/compose/docker-compose.yml`. The compose
defaults intentionally keep `POSTGRES_DUAL_WRITE_ENABLED=false` and
`POSTGRES_READ_ENABLED=false`; move through the switch states below instead of
enabling PostgreSQL primary read at container creation time.

Use the phase override env files when changing Docker Compose switch states.
They override only the migration/read and startup-ingest flags while keeping
connection settings in the normal deployment `.env`:

```bash
# Enter dual-write: Mongo primary read/write, PostgreSQL replay enabled.
docker compose --env-file .env --env-file deploy/env/postgres-dual-write.env \
  -f <compose-file> up -d backend

# Enter PostgreSQL-read with Mongo fallback after all pre-read gates pass.
docker compose --env-file .env --env-file deploy/env/postgres-read.env \
  -f <compose-file> up -d backend
```

`deploy/env/postgres-dual-write.env` sets `POSTGRES_DUAL_WRITE_ENABLED=true`,
`POSTGRES_READ_ENABLED=false`, `POSTGRES_DUAL_WRITE_FAIL_OPEN=true`, and
`SYNC_STOCK_BASICS_ENABLED=false`. `deploy/env/postgres-read.env` sets
`POSTGRES_DUAL_WRITE_ENABLED=true`, `POSTGRES_READ_ENABLED=true`,
`POSTGRES_DUAL_WRITE_FAIL_OPEN=false`, and `SYNC_STOCK_BASICS_ENABLED=false`.
Disabling startup stock basics during cutover prevents background imports from
changing Mongo/PostgreSQL counts while evidence is being collected.

For Docker Compose deployments, run migration commands inside the backend
container so they use the same image, code, and mounted environment as the
service. Replace `<compose-file>` with the compose variant in use:

```bash
docker compose -f <compose-file> exec backend sh -lc \
  'cd /app/backend && alembic -c alembic.ini upgrade head'

docker compose -f <compose-file> exec backend sh -lc \
  'cd /app && python -m app.db.mongo_to_postgres_migrator'

mkdir -p runtime/logs/postgres-cutover/pre-read
docker compose -f <compose-file> logs --no-color backend \
  > runtime/logs/postgres-cutover/pre-read/backend.log

docker compose -f <compose-file> exec backend sh -lc \
  'cd /app && python backend/scripts/postgres_cutover_gate.py --require-explicit-env --target-env <target-env> --target-phase pre-read --skip-api-smoke --runtime-log /app/logs/postgres-cutover/pre-read/backend.log --output-dir /app/logs/postgres-cutover/pre-read'

docker compose -f <compose-file> exec backend sh -lc \
  'cd /app && python backend/scripts/postgres_cutover_evidence_check.py --require-target-manifest --expected-phase pre-read --require-runtime-log-check /app/logs/postgres-cutover/pre-read'
```

Recommended evidence-bundle command for target environments:

```bash
mkdir -p /tmp/tradingagents_postgres_cutover_evidence/pre-read
docker compose -f <compose-file> logs --no-color backend \
  > /tmp/tradingagents_postgres_cutover_evidence/pre-read/backend.log

# Copy and fill the non-secret pre-read template outside git:
# cp deploy/env-templates/postgres-pre-read-evidence.env.example /secure/path/postgres-pre-read-evidence.env
set -a; . /secure/path/postgres-pre-read-evidence.env; set +a

python backend/scripts/postgres_cutover_gate.py \
  --require-explicit-env \
  --skip-api-smoke \
  --runtime-log /tmp/tradingagents_postgres_cutover_evidence/pre-read/backend.log \
  --output-dir /tmp/tradingagents_postgres_cutover_evidence/pre-read

python backend/scripts/postgres_cutover_evidence_check.py \
  --require-target-manifest \
  --expected-phase pre-read \
  --require-runtime-log-check \
  /tmp/tradingagents_postgres_cutover_evidence/pre-read
```

Runtime log evidence should be saved beside the bundle and passed to
`postgres_cutover_gate.py --runtime-log`. Successful dual-write events are
emitted at `INFO`, so the default Docker Compose log level is sufficient. The
standalone `postgres_runtime_log_check.py` script remains available for
diagnostics, but target acceptance should prefer the integrated gate command so
`summary.json` records the runtime log step.

The project Docker Compose files mount `runtime/logs` to `/app/logs`. If a
custom deployment does not mount that path, either run the evidence command on
the host with the host log path or copy the log into a container-readable
evidence directory before using `--runtime-log`.

Use `--compile-only-query-plan` only before PostgreSQL is reachable. Use `--skip-api-smoke` only before the deployed service is switched to `POSTGRES_READ_ENABLED=true`; API smoke must still be run after enabling PostgreSQL read and before accepting the cutover.

The gate runner saves command output plus `summary.json` without writing secrets. It does not change feature flags, restart services, delete data, or authorize moving to the next switch state by itself. It treats successful process exit as insufficient: JSON outputs must also satisfy the inventory, consistency, query-plan, data-path smoke, and, when included, API smoke acceptance fields. The following steps remain the source-of-truth sequence and stop conditions.

`--require-explicit-env` is recommended for target environments. It fails before
running any gate when MongoDB, PostgreSQL, or required API smoke credentials are
missing. It also requires an explicit target environment label and cutover
phase via `--target-env/--target-phase` or `TRADINGAGENTS_TARGET_ENV` /
`TRADINGAGENTS_CUTOVER_PHASE`, and writes only redacted environment state to the
evidence bundle.
With `--require-explicit-env`, the gate also enforces phase shape: `pre-read`
must use `--skip-api-smoke`, `post-read` must include API smoke, and `rollback`
must use `postgres_rollback_check.py` instead of `postgres_cutover_gate.py`.

For repeatable local seeded verification before touching a target environment:

```bash
python backend/scripts/postgres_local_cutover_verify.py \
  --output-dir /tmp/tradingagents_postgres_local_cutover
```

This local script creates disposable Docker MongoDB/PostgreSQL containers, seeds one
representative document for every hot collection, applies schema, runs the migrator,
and then executes the cutover gate. It is not a substitute for target-environment
evidence.
The nested gate writes `gate/00_target_manifest.json` with
`target_env=local-seeded`; use this only to verify evidence-bundle shape before
running the same gates against a real target environment. The local verifier
also runs `postgres_cutover_evidence_check.py` as its final step, so the command
fails if the nested gate bundle is incomplete.

```bash
python backend/scripts/postgres_cutover_evidence_check.py \
  --require-target-manifest \
  --expected-phase pre-read \
  /tmp/tradingagents_postgres_local_cutover/gate
```

If a real backend log is available, pass it through the nested cutover gate
without fabricating log content:

```bash
python backend/scripts/postgres_local_cutover_verify.py \
  --output-dir /tmp/tradingagents_postgres_local_cutover \
  --runtime-log /path/to/backend.log
```

1. Confirm dependencies and static migration inventory:

```bash
python backend/scripts/postgres_migration_inventory.py
```

Required:

- `response_model_dict_endpoints=0`
- `raw_dict_request_bodies=0`
- every remaining Mongo collection is covered by `docs/migration/postgres_long_tail_coverage.md`
- the inventory command exits non-zero by default when router contract regressions are present; use `--allow-contract-regressions` only for exploratory reporting, not cutover approval

2. Confirm migration SQL can be generated:

```bash
cd backend
alembic -c alembic.ini upgrade head --sql > /tmp/tradingagents_postgres_offline.sql
wc -l /tmp/tradingagents_postgres_offline.sql
```

3. Confirm tests:

```bash
python backend/scripts/postgres_test_gate.py --scope quick
```

Use scoped gates during migration work instead of running the whole backend test
suite after every small edit:

```bash
# Router/OpenAPI/Pydantic contract changes
python backend/scripts/postgres_test_gate.py --scope api-contract

# Cutover/evidence/runtime-log script changes
python backend/scripts/postgres_test_gate.py --scope cutover

# Rollback/API-smoke migration-state changes
python backend/scripts/postgres_test_gate.py --scope rollback

# DB/session/migrator/repository changes
python backend/scripts/postgres_test_gate.py --scope db

# Documentation/runbook/deploy-template changes
python backend/scripts/postgres_test_gate.py --scope docs
```

Run the expensive full backend suite only as the final local gate before
handing off or accepting the migration branch:

```bash
python backend/scripts/postgres_test_gate.py --scope full
```

4. Confirm startup workers and scheduled jobs are explicitly gated for the cutover state.

Required:

- `SYNC_STOCK_BASICS_ENABLED=false` in environments where the cutover smoke must not import fresh external stock basics during startup.
- startup logs show the stock basic information sync is disabled before API smoke begins.
- no worker or scheduler remains Mongo-only for hot/status collections listed in `docs/migration/postgres_hot_field_matrix.md`.
- if any worker must run during soak, prove its writes through dual-write or pause that worker before enabling PostgreSQL read.

## Migration Steps

1. Start in `mongo` state and take a Mongo backup.

2. Apply PostgreSQL schema:

```bash
cd backend
alembic -c alembic.ini upgrade head
```

3. Run the Mongo to PostgreSQL migrator. Use the environment for the target Mongo/PostgreSQL endpoints:

```bash
cd backend
python -m app.db.mongo_to_postgres_migrator
```

4. Enable dual-write:

```bash
POSTGRES_DUAL_WRITE_ENABLED=true
POSTGRES_READ_ENABLED=false
```

Docker Compose equivalent:

```bash
docker compose --env-file .env --env-file deploy/env/postgres-dual-write.env \
  -f <compose-file> up -d backend
```

5. Exercise worker and user-write flows long enough to prove new writes appear in both stores.

   If a startup or scheduled worker is intentionally disabled for cutover, record the disabled flag and log evidence. Disabled workers must have a separate replay/backfill decision before normal operations resume.

6. Run consistency check:

```bash
python backend/scripts/postgres_consistency_check.py --sample-limit 500
```

Required before read cutover:

- `all_consistent=true`
- zero `missing_in_postgres`
- zero unexpected `extra_in_postgres`
- acceptable `count_delta=0` for hot collections
- the consistency command exits non-zero by default when `all_consistent=false`; use `--allow-inconsistent` only for diagnostic report collection after a failed gate

7. Collect representative query plans:

```bash
python backend/scripts/postgres_query_plan_check.py
```

Required:

- `all_required_without_payload_filter=true`
- representative high-frequency queries filter by split columns, not `payload`
- review the JSON plan output for unexpected sequential scans on large hot tables

Use this when PostgreSQL is not reachable yet:

```bash
python backend/scripts/postgres_query_plan_check.py --compile-only
```

8. Run PostgreSQL data-path smoke against the migrated target database:

```bash
python backend/scripts/postgres_cutover_smoke.py --pretty
```

Required:

- `all_passed=true`
- stock, quote, historical quote, financial, analysis, user preference, paper trading, operation log, news, message, security/session, and system config checks pass
- failures must be treated as cutover blockers unless the corresponding Mongo collection is explicitly documented as empty in the target environment

9. Enable PostgreSQL read with Mongo fallback:

```bash
POSTGRES_DUAL_WRITE_ENABLED=true
POSTGRES_READ_ENABLED=true
```

Docker Compose equivalent:

```bash
docker compose --env-file .env --env-file deploy/env/postgres-read.env \
  -f <compose-file> up -d backend
```

10. Run core API smoke checks against the deployed service:

```bash
# Copy and fill the non-secret template outside git with target credentials:
# cp deploy/env-templates/postgres-post-read-smoke.env.example /secure/path/postgres-post-read-smoke.env
# set -a; . /secure/path/postgres-post-read-smoke.env; set +a

TRADINGAGENTS_API_BASE_URL=https://<target-host> \
TRADINGAGENTS_API_USERNAME=<smoke-user> \
TRADINGAGENTS_API_PASSWORD=<smoke-password> \
TRADINGAGENTS_SMOKE_STOCK_CODE=000001 \
TRADINGAGENTS_SMOKE_SYMBOL=000001 \
TRADINGAGENTS_SMOKE_TASK_ID=<optional-existing-task-id> \
TRADINGAGENTS_EXPECT_POSTGRES_READ_ENABLED=true \
TRADINGAGENTS_EXPECT_POSTGRES_DUAL_WRITE_ENABLED=true \
python backend/scripts/postgres_api_smoke.py --pretty
```

Alternatively provide `TRADINGAGENTS_API_TOKEN` instead of username/password.
The smoke identity must be allowed to call `/api/system/config/summary`; the
optional migration-state check uses that endpoint to prove the deployed service
is running with the expected PostgreSQL read/write switches.

To append API smoke into a final cutover evidence bundle after PostgreSQL read is enabled:

```bash
# Reuse the filled post-read smoke env file so API credentials, target label,
# and expected migration switches stay consistent across commands.
set -a; . /secure/path/postgres-post-read-smoke.env; set +a

TRADINGAGENTS_EXPECT_POSTGRES_READ_ENABLED=true \
TRADINGAGENTS_EXPECT_POSTGRES_DUAL_WRITE_ENABLED=true \
python backend/scripts/postgres_cutover_gate.py \
  --require-explicit-env \
  --target-env <target-env> \
  --target-phase post-read \
  --runtime-log /tmp/tradingagents_postgres_cutover_evidence/post-read/backend.log \
  --output-dir /tmp/tradingagents_postgres_cutover_evidence/post-read

python backend/scripts/postgres_cutover_evidence_check.py \
  --require-target-manifest \
  --expected-phase post-read \
  --require-api-smoke \
  --require-api-migration-state \
  --require-runtime-log-check \
  /tmp/tradingagents_postgres_cutover_evidence/post-read
```

Docker Compose equivalent:

```bash
mkdir -p runtime/logs/postgres-cutover/post-read
docker compose -f <compose-file> logs --no-color backend \
  > runtime/logs/postgres-cutover/post-read/backend.log

docker compose -f <compose-file> exec backend sh -lc \
  'cd /app && python backend/scripts/postgres_cutover_gate.py --require-explicit-env --target-env <target-env> --target-phase post-read --runtime-log /app/logs/postgres-cutover/post-read/backend.log --output-dir /app/logs/postgres-cutover/post-read'

docker compose -f <compose-file> exec backend sh -lc \
  'cd /app && python backend/scripts/postgres_cutover_evidence_check.py --require-target-manifest --expected-phase post-read --require-api-smoke --require-api-migration-state --require-runtime-log-check /app/logs/postgres-cutover/post-read'
```

If runtime logs must be checked independently for diagnostics, use the same
strict script and still require the generated file in the evidence checker:

```bash
python backend/scripts/postgres_runtime_log_check.py \
  /tmp/tradingagents_postgres_cutover_evidence/post-read/backend.log \
  > /tmp/tradingagents_postgres_cutover_evidence/post-read/runtime_log_check.json

python backend/scripts/postgres_cutover_evidence_check.py \
  --require-target-manifest \
  --expected-phase post-read \
  --require-api-smoke \
  --require-api-migration-state \
  --require-runtime-log-check \
  /tmp/tradingagents_postgres_cutover_evidence/post-read
```

Required:

- `all_passed=true`
- evidence bundle check passes with `--require-api-smoke --require-api-migration-state`
- auth login or bearer token validates `/api/auth/me`
- public health/model/data endpoints pass
- authenticated stock, market, financial, favorites, tags, paper, operation log, news, config endpoints pass
- analysis task API checks pass when `TRADINGAGENTS_SMOKE_TASK_ID` is provided; otherwise the analysis task check is recorded as `skipped`
- MongoDB counts for seeded smoke collections do not unexpectedly grow from startup-only background imports when those imports are disabled.

The checked endpoint groups are:

- auth login and current user
- stock basic info, stock list, market quote, daily quotes
- financial data
- screening
- favorites and tags
- paper account, positions, orders
- operation logs list, stats, CSV export
- analysis task status, result, user history
- news query
- internal/social message query, search, stats

## Rollback

If read cutover fails:

1. Set:

```bash
POSTGRES_READ_ENABLED=false
POSTGRES_DUAL_WRITE_ENABLED=true
```

2. Restart the application service.

3. Confirm the failing API succeeds from Mongo read.

4. Keep dual-write enabled if PostgreSQL writes are healthy; otherwise set `POSTGRES_DUAL_WRITE_ENABLED=false` and schedule replay after repair.

5. Re-run:

```bash
mkdir -p /tmp/tradingagents_postgres_cutover_evidence/rollback

# Copy and fill the non-secret rollback template outside git with target credentials:
# cp deploy/env-templates/postgres-rollback-smoke.env.example /secure/path/postgres-rollback-smoke.env
set -a; . /secure/path/postgres-rollback-smoke.env; set +a
# The rollback template must keep these expected runtime switches unless
# postgres_rollback_check.py --allow-dual-write-disabled is explicitly used:
# TRADINGAGENTS_EXPECT_POSTGRES_READ_ENABLED=false
# TRADINGAGENTS_EXPECT_POSTGRES_DUAL_WRITE_ENABLED=true

python backend/scripts/postgres_api_smoke.py --pretty \
  > /tmp/tradingagents_postgres_cutover_evidence/rollback/api_smoke.json

python backend/scripts/postgres_consistency_check.py --sample-limit 500 \
  > /tmp/tradingagents_postgres_cutover_evidence/rollback/consistency.json

POSTGRES_READ_ENABLED=false \
POSTGRES_DUAL_WRITE_ENABLED=true \
python backend/scripts/postgres_rollback_check.py \
  --api-smoke-json /tmp/tradingagents_postgres_cutover_evidence/rollback/api_smoke.json \
  --consistency-json /tmp/tradingagents_postgres_cutover_evidence/rollback/consistency.json \
  --output-dir /tmp/tradingagents_postgres_cutover_evidence/rollback \
  --target-env "$TRADINGAGENTS_TARGET_ENV" \
  > /tmp/tradingagents_postgres_cutover_evidence/rollback/rollback_check.json

# The rollback check fails with structured JSON when neither --target-env nor
# TRADINGAGENTS_TARGET_ENV is present.

python backend/scripts/postgres_cutover_evidence_check.py \
  --rollback-only \
  --require-target-manifest \
  --expected-phase rollback \
  --require-rollback-check \
  /tmp/tradingagents_postgres_cutover_evidence/rollback
```

If PostgreSQL writes are unhealthy and dual-write must be disabled during
rollback, use `POSTGRES_DUAL_WRITE_ENABLED=false` plus
`postgres_rollback_check.py --allow-dual-write-disabled`; this creates an
explicit replay follow-up requirement in the rollback evidence instead of
silently accepting a partial rollback state.

Do not drop PostgreSQL tables during rollback. Schema rollback is not required to return to Mongo primary read.

## Observability Requirements

- Dual-write failures must log collection, legacy/business key, status, and reason.
- Runtime log checking with `backend/scripts/postgres_runtime_log_check.py` must pass in the target evidence bundle; strict mode requires startup sync-disable evidence, at least one successful dual-write event, zero dual-write failures, and zero Mongo-only migration warnings.
- Consistency output must be saved with deployment evidence.
- Query plan output must be saved before entering `postgres_read_mongo_fallback`.
- PostgreSQL data-path smoke output must be saved before entering `postgres_read_mongo_fallback`.
- Startup worker gate logs must be saved before entering `postgres_read_mongo_fallback`.
- API smoke output must be saved after entering `postgres_read_mongo_fallback` and before accepting the cutover as complete.
- Target evidence bundles must include `00_target_manifest.json` with the target environment label and the phase (`pre-read`, `post-read`, or `rollback`); evidence checks should use `--require-target-manifest --expected-phase <phase>`.
- Rollback drill output must include `rollback_check.json` and pass `postgres_cutover_evidence_check.py --rollback-only --require-target-manifest --expected-phase rollback --require-rollback-check` before the target migration is declared fully reversible.
- Any deliberate Mongo-only collection must remain listed in `postgres_long_tail_coverage.md`.

## Stop Conditions

Do not move from `dual_write` to `postgres_read_mongo_fallback` when any of these are true:

- consistency check is missing or `all_consistent=false`
- worker writes are still Mongo-only for a hot/status collection
- startup workers import or mutate Mongo collections despite their disable flags
- startup/scheduler gating evidence is missing for workers paused during cutover
- representative query plans use `payload` filters for high-frequency paths
- PostgreSQL data-path smoke is missing or `all_passed=false`
- PostgreSQL migration cannot be re-run idempotently

## Post-Read Acceptance Conditions

After entering `postgres_read_mongo_fallback`, do not accept the cutover as
complete when any of these are true:

- API smoke is missing or `all_passed=false`
- evidence bundle check with `--require-target-manifest --expected-phase post-read --require-api-smoke --require-api-migration-state` fails
- runtime log check is missing or fails after PostgreSQL read is enabled
- auth/user/account/trading paths have no validated fallback evidence
- MongoDB hot collection counts grow unexpectedly from startup-only background imports while those imports are disabled
