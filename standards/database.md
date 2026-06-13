# Database Standard

## Scope

Use this standard when changing SQLAlchemy models, queries, sessions, transactions, repositories, migrations, database constraints, database tests, or query performance.

## Core Rules

- Follow existing SQLAlchemy and Alembic patterns.
- Keep transaction ownership explicit.
- Do not hide database failures behind broad fallbacks.
- Keep persistence details behind repositories or the existing project-owned data boundary.
- Schema changes require an Alembic migration unless the user explicitly requests implementation-only work.

## Async Session Rules

- Use `AsyncSession` consistently in async backend paths.
- Do not mix blocking database calls into async request handling.
- Do not call `asyncio.run()` inside application code that may already run in an event loop.
- Avoid lazy-loading behavior that causes unexpected async I/O outside the intended data access boundary.

## Transaction Ownership

- The owner of the transaction controls commit and rollback.
- Helpers and repositories should not call `commit()` unless their contract explicitly owns the transaction.
- Prefer `flush()` when generated IDs or constraint checks are needed inside an existing transaction.
- Roll back only in the scope that owns the session or transaction.
- Do not scatter rollback logic across unrelated helpers.

## Repository Rules

Repositories should hide:

- SQLAlchemy query details;
- relationship loading choices;
- persistence-specific error translation;
- ORM-to-domain or ORM-to-DTO mapping when that is the existing pattern.

Repositories should not own unrelated business policy unless the existing project pattern combines those responsibilities.

## Query Rules

- Use SQLAlchemy expressions or bound parameters. Avoid raw SQL string interpolation.
- Keep queries readable and scoped to the repository or data-access owner.
- Avoid N+1 query patterns in new code.
- Use existing eager-loading strategies when returning related data.
- Paginate or bound queries that can grow.
- Select only the data needed when large rows or relationships are involved.

## Constraints And Invariants

- Enforce critical invariants at the strongest appropriate layer.
- Use database constraints for uniqueness, foreign keys, and integrity guarantees that must survive concurrency.
- Use service/domain validation for business rules that require context.
- Translate expected constraint failures into domain or API errors at the owning boundary.

## Alembic Migrations

- Keep migrations focused on one schema concern.
- Use project migration naming and async/sync setup conventions.
- Include both `upgrade` and `downgrade` when the project expects downgrade support.
- Do not include destructive or data-losing migrations unless explicitly requested and documented.
- For backfills or data migrations, make behavior deterministic and safe for repeated deployment patterns when possible.
- Do not edit old migrations unless the task explicitly targets migration history before release.

## Tenant And Authorization Scope

When the application has organizations, tenants, projects, users, or ownership scopes:

- include the scope in queries that read or mutate protected resources;
- do not rely on frontend-provided scope alone;
- test cross-tenant or cross-owner denial for protected data;
- avoid helper functions that fetch by ID without the required owner/scope when used in protected paths.

## Error Translation

- Catch expected database errors narrowly.
- Preserve original causes when translating errors.
- Do not expose raw database errors in public API responses.
- Let unexpected database errors fail through the application error boundary with safe logging.

## Database Tests

- Use isolated test databases, schemas, transactions, or fixtures according to the existing project pattern.
- Keep test data minimal but realistic.
- Test important constraints, relationship loading, transaction behavior, and tenant scope at integration level.
- Do not point tests at development, staging, or production databases.

## Performance Rules

- Check for N+1 queries when returning lists or related entities.
- Use indexes for new query patterns that filter, sort, or join on growing tables.
- Avoid unbounded deletes or updates unless intentionally scoped.
- Prefer database-side filtering and pagination over loading large datasets into Python.

## Review Checklist

- Is transaction ownership clear?
- Did any helper call `commit()` without owning the transaction?
- Are queries scoped, bounded, and safe from injection?
- Are relationship loading choices intentional?
- Are constraints enforced in the correct layer?
- Does the migration match the model change?
- Are destructive changes explicitly requested and documented?
- Are database tests isolated and meaningful?
