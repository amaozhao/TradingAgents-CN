# Engineering Standards Index

This directory contains engineering standards that agents and maintainers should read when a task touches the relevant area. The root `AGENTS.md` stays short and acts as the entry point; this directory holds the detailed rules, review questions, and examples.

## Use Model

1. Read `AGENTS.md` first.
2. Identify the areas touched by the task.
3. Read only the relevant standard files before editing those areas.
4. Apply the most specific standard when rules overlap.
5. Keep final reports grounded in what changed and what verification actually ran.

## Selection Guide

Read the smallest set of standards that covers the change:

| Task touches | Read |
| --- | --- |
| services, repositories, adapters, API clients, hooks, feature boundaries, shared contracts | `modules.md` |
| tests, fixtures, mocks, test layout, verification commands | `testing.md` |
| Python or TypeScript types, schemas, DTOs, boundary models, untrusted data | `typing.md` |
| `try`/`except`/`catch`, fallbacks, retries, logging, exception mapping | `errors.md` |
| API routes, frontend API clients, request/response shapes, status codes, pagination | `contracts.md` |
| SQLAlchemy, transactions, repositories, migrations, database tests | `database.md` |
| Next.js, React, forms, hooks, Tailwind, accessibility, UI state | `frontend.md` |
| auth, authorization, secrets, uploads, redirects, webhooks, SSRF, XSS | `security.md` |
| dependencies, lockfiles, env vars, runtime config, feature flags, logs, background work | `operations.md` |
| query cost, payload size, caching, external calls, async throughput, rendering, bundle size | `performance.md` |
| review, final self-review, diff scope, verification reporting | `review.md` |

If a task spans multiple areas, read each relevant standard. If two standards overlap, follow the more specific rule for the touched code.

## File Map

- `modules.md`: deep modules, SOLID-compatible boundaries, invariant ownership, shallow wrappers, god modules.
- `testing.md`: backend and frontend test tiers, mirrored paths, fixtures, mocks, async tests, database tests, verification.
- `typing.md`: Python typing, TypeScript typing, DTOs, schemas, untrusted data, `Any` and `any` restrictions.
- `errors.md`: `try`/`except`/`catch`, expected vs unexpected failures, fallbacks, retries, error translation.
- `contracts.md`: backend/frontend API contracts, status codes, request/response models, error formats, pagination.
- `database.md`: SQLAlchemy, AsyncSession, transactions, repositories, migrations, constraints, query performance.
- `frontend.md`: Next.js, React, hooks, forms, state, Tailwind, accessibility, UI behavior.
- `security.md`: authentication, authorization, tenant isolation, secrets, injection risks, uploads, redirects, privacy.
- `operations.md`: dependency changes, configuration, feature flags, logging, metrics, tracing, background work, operational diagnostics.
- `performance.md`: query performance, payload size, caching, external calls, async throughput, rendering, bundle size.
- `review.md`: review flow, checklist, final response format, verification expectations.

## What Belongs Here

Put a rule in `standards/` when it is:

- durable across many tasks;
- specific enough to guide code changes;
- too detailed for the root `AGENTS.md`;
- useful during implementation or review.

Do not put one-off product requirements, implementation plans, runbooks, ADR history, or tutorials here. Product requirements belong in specs or issues. Deployment procedures belong in runbooks. Historical decisions belong in ADRs or decision records.

## Standard File Format

Each standard should normally include:

```text
# <Area> Standard
## Scope
## Core Rules
## Targeted Rules
## Tests Or Verification
## Review Checklist
```

Keep standards actionable. Prefer concrete rules and short examples over long explanations.

## Maintenance Rules

- Keep file names lowercase single words.
- Merge highly overlapping standards instead of creating thin files.
- Add a new standard only when the area is repeatedly relevant or too large for an existing file.
- Keep examples project-shaped: Python + FastAPI + SQLAlchemy + Alembic + pytest, and Next.js + React + TypeScript + Tailwind + Vitest.
- Update `AGENTS.md` when adding or removing a standard so agents know when to read it.
