# PostgreSQL Long-Tail Coverage

Generated from `docs/migration/postgres_inventory.json` and manual code review.

## Covered Or Mapped

| Mongo collection | PostgreSQL target | Strategy | Status |
| --- | --- | --- | --- |
| `stock_basic_info_hk` | `stock_basic_info` | Normalize to shared `code/source` table; payload keeps HK-specific fields. | covered |
| `stock_basic_info_us` | `stock_basic_info` | Normalize to shared `code/source` table; payload keeps US-specific fields. | covered |
| `market_quotes_hk` | `market_quotes` | Normalize to shared `code/source` table. | covered |
| `market_quotes_us` | `market_quotes` | Normalize to shared `code/source` table. | covered |
| `stock_news` | `stock_news` | JSONB-first table with `symbol/publish_time/data_source/category/sentiment/importance` split. | covered |
| `scheduler_history` | `scheduler_history` | JSONB-first table with `job_id/action/status/timestamp` split. | covered |
| `scheduler_metadata` | `scheduler_metadata` | JSONB-first table with unique `job_id`. | covered |
| `analysis_batches` | `analysis_batches` | JSONB-first table with `batch_id/user_id/status/total_tasks` split. | covered |
| `analysis_results` | `analysis_results` | JSONB-first table for legacy result documents and cleanup tombstones. | covered |
| `users_collection` | `user_accounts` | Static scanner alias for `UserService.users_collection`. | covered |
| `notifications` | `notifications` | JSONB-first table with `user_id/type/status/severity/title` split; create/read-status/delete cleanup tombstones dual-write. | covered |
| `token_usage` | `token_usage` | JSONB-first table with provider/model/session/time/token/cost columns; add/delete cleanup tombstones dual-write. | covered |
| `internal_messages` | `internal_messages` | JSONB-first table keyed by `message_id`; common filtering fields split and bulk upserts dual-write. | covered |
| `social_media_messages` | `social_media_messages` | JSONB-first table keyed by `message_id/platform`; common filtering fields split and bulk upserts dual-write. | covered |
| `stock_daily_quotes` | `stock_daily_quotes` | Historical time-series table keyed by `symbol/trade_date/data_source/period`; `HistoricalDataService` bulk writes dual-write standardized daily quotes. | covered |
| `quotes_ingestion_status` | `sync_status` | Real-time quote ingestion status is normalized into the shared status table as `job=quotes_ingestion`. | covered |
| `user_sessions` | `user_sessions` | JSONB-first security/session table keyed by `session_id`; `user_id/username/ip_address/expires_at/last_activity_at/deleted` split and cleanup tombstones dual-write. | covered |
| `login_attempts` | `login_attempts` | JSONB-first security audit table keyed by `legacy_id`; `user_id/username/ip_address/success/reason/timestamp/deleted` split and cleanup tombstones dual-write. | covered |
| `stock_daily_quotes_hk` / `stock_daily_quotes_us` | `stock_daily_quotes` | Read-only aliases in `UnifiedStockService.collection_map`; no application write path found. Main-read repository must filter by `market` instead of keeping per-market physical tables. | mapped for read cutover |
| Backup import for migrated collections | Existing PG target per collection | Import replay dual-writes only collections in `HOT_COLLECTIONS`; overwrite imports write tombstones before Mongo delete. | covered |
| Backup import for unknown collections | Mongo only | Import remains allowed for arbitrary ad-hoc collections, but logs `database_import_unsupported_collection` and does not claim PG coverage. | explicit Mongo-only |
| Provider initialization script | `system_config_documents` | `init_providers.py` writes old `llm_providers` tombstones before Mongo cleanup and dual-writes every inserted provider document. | covered |
| Provider-key normalization script | `system_config_documents` | `normalize_provider_keys.py` dual-writes `llm_providers`, `system_configs`, and `model_catalog` replacements plus duplicate tombstones. | covered |

## Explicitly Retained Read-Only Path

| Mongo collection or dynamic source | Current evidence | Required next action |
| --- | --- | --- |
| Backup export for unknown collections | Export is read-only and may include arbitrary Mongo collections. | No PG write needed; keep as Mongo export until all collection read paths are cut over. |

## Dynamic Write Audit

The static scanner intentionally reports `collection=null` when it cannot prove
the target collection name from local AST context. Each unresolved write below
has been manually reviewed and must remain listed until the scanner can resolve
it automatically.

| Source | Line | Operation | Runtime target | PostgreSQL decision |
| --- | ---: | --- | --- | --- |
| `app/scripts/migrate_mongo_db.py` | 123 | `replace_one` | Source/destination collection selected by the one-off migration script loop. | Operator-only Mongo migration utility; not part of service cutover and must not run during PostgreSQL read cutover. |
| `app/scripts/migrate_mongo_db.py` | 128 | `replace_one` | Source/destination collection selected by the one-off migration script loop. | Operator-only Mongo migration utility; not part of service cutover and must not run during PostgreSQL read cutover. |
| `app/services/database/backups.py` | 360 | `delete_many` | Multi-collection import `coll_name`. | For HOT_COLLECTIONS, overwrite first writes tombstones to PostgreSQL; unknown collections are explicit Mongo-only import with warning. |
| `app/services/database/backups.py` | 377 | `insert_many` | Multi-collection import `coll_name`. | For HOT_COLLECTIONS, import replay dual-writes documents to PostgreSQL; unknown collections are explicit Mongo-only import with warning. |
| `app/services/database/backups.py` | 412 | `delete_many` | Single-collection import `collection`. | For HOT_COLLECTIONS, overwrite first writes tombstones to PostgreSQL; unknown collections are explicit Mongo-only import with warning. |
| `app/services/database/backups.py` | 428 | `insert_many` | Single-collection import `collection`. | For HOT_COLLECTIONS, import replay dual-writes documents to PostgreSQL; unknown collections are explicit Mongo-only import with warning. |
| `app/services/internal_message_service.py` | 137 | `bulk_write` | `internal_messages` via `_get_collection()`. | Covered by `dual_write_hot_documents("internal_messages", ...)`. |
| `app/services/news_data_service.py` | 217 | `bulk_write` | `stock_news` via `_get_collection()`. | Covered by `_dual_write_news(...)` into `stock_news`. |
| `app/services/news_data_service.py` | 722 | `delete_many` | `stock_news` via `_get_collection()`. | Covered by `_dual_write_news_tombstones(...)` into `stock_news`. |
| `app/services/quotes_ingestion_service.py` | 429 | `bulk_write` | `market_quotes` via `self.collection_name`. | Covered by `dual_write_hot_documents("market_quotes", ...)`; status writes use `dual_write_hot_document("quotes_ingestion_status", ...)` -> `sync_status`. |
| `app/services/social_media_service.py` | 117 | `bulk_write` | `social_media_messages` via `_get_collection()`. | Covered by `dual_write_hot_documents("social_media_messages", ...)`. |

## Operator Script Write Audit

Operator scripts can still be run manually during a migration window, so every
script-level Mongo write must have an explicit PostgreSQL decision even when the
collection is statically known.

| Source | Line | Operation | Mongo collection | PostgreSQL decision |
| --- | ---: | --- | --- | --- |
| `app/scripts/init_providers.py` | 143 | `delete_many` | `llm_providers` | Covered by `dual_write_hot_documents("llm_providers", tombstones)` before Mongo cleanup. |
| `app/scripts/init_providers.py` | 152 | `insert_one` | `llm_providers` | Covered by `dual_write_hot_document("llm_providers", provider_data)` after Mongo insert. |
| `app/scripts/migrate_mongo_db.py` | 123 | `replace_one` | dynamic source/target collection | Operator-only Mongo migration utility; not part of service cutover and must not run during PostgreSQL read cutover. |
| `app/scripts/migrate_mongo_db.py` | 128 | `replace_one` | dynamic source/target collection | Operator-only Mongo migration utility; not part of service cutover and must not run during PostgreSQL read cutover. |
| `app/scripts/normalize_provider_keys.py` | 109 | `replace_one` | `llm_providers` | Covered by `_dual_write_document("llm_providers", final_doc)` after Mongo replacement. |
| `app/scripts/normalize_provider_keys.py` | 126 | `delete_many` | `llm_providers` | Covered by `_dual_write_documents("llm_providers", tombstones)` before deleting duplicates. |
| `app/scripts/normalize_provider_keys.py` | 158 | `update_one` | `system_configs` | Covered by `_dual_write_document("system_configs", updated_doc)` after Mongo update. |
| `app/scripts/normalize_provider_keys.py` | 196 | `replace_one` | `model_catalog` | Covered by `_dual_write_document("model_catalog", updated)` after Mongo replacement. |
| `app/scripts/normalize_provider_keys.py` | 212 | `delete_many` | `model_catalog` | Covered by `_dual_write_documents("model_catalog", tombstones)` before deleting duplicates. |

## Cutover Rule

No dynamic Mongo write can be treated as safe merely because the static scanner reports `None`. Each dynamic write must have a row in this file with one of: PostgreSQL target, deliberate Mongo-only retention reason, or a blocking follow-up task.
