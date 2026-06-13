# Project Agent Instructions

These instructions apply to the whole repository unless a deeper `AGENTS.md` overrides them for files under its directory.

## General

- Do not commit or push changes unless the user explicitly asks for it in the current task.
- Keep changes small, reviewable, and scoped to the user's request.
- Prefer existing project patterns over new abstractions.
- Inspect existing implementation, configuration, tests, and public contracts before changing architecture, dependencies, test layout, build tooling, or API behavior.
- Do not edit generated, vendored, cache, runtime, log, build, coverage, or dependency output unless the task explicitly targets it.
- Avoid unrelated formatting churn. Format only files affected by the task unless the user asks for broader cleanup.
- Keep specifications, tests, implementation, and documentation consistent.
- When fixing a bug, identify the owning invariant and root cause first. Do not hide the failure behind broad fallback logic.

## Standards

Read the relevant standard before changing affected code:

- `standards/modules.md`: services, repositories, adapters, API clients, hooks, feature boundaries, shared contracts, or substantial component boundaries.
- `standards/testing.md`: tests, fixtures, mocks, test layout, test data, or verification strategy.
- `standards/typing.md`: Python typing, TypeScript typing, schemas, DTOs, API types, React props, or untrusted data.
- `standards/errors.md`: error handling, `try`/`except`/`catch`, logging, fallbacks, retries, or exception mapping.
- `standards/contracts.md`: backend API routes, frontend API clients, request/response schemas, status codes, pagination, or error response formats.
- `standards/database.md`: SQLAlchemy models, queries, sessions, transactions, migrations, or database tests.
- `standards/frontend.md`: React components, hooks, forms, state, Next.js server/client boundaries, UI behavior, Tailwind, or accessibility.
- `standards/security.md`: authentication, authorization, secrets, tenant isolation, uploads, redirects, SSRF, XSS, or untrusted input.
- `standards/operations.md`: dependencies, package changes, lockfiles, environment variables, runtime configuration, feature flags, logging, metrics, tracing, background work, or operational diagnostics.
- `standards/performance.md`: query performance, payload size, caching, external calls, async throughput, rendering, bundle size, or latency-sensitive paths.
- `standards/review.md`: code review, final self-review, diff review, or change risk assessment.

If standards conflict, follow the more specific standard for the touched code. If a deeper `AGENTS.md` conflicts with these root rules, follow the deeper file for its subtree.

## Naming

- Project-owned file and directory names must be a single real word.
- Use lowercase ASCII words by default.
- Do not create fake compound words such as `loaddata`, `runagent`, `fetchreport`, or verb-plus-noun concatenations.
- Avoid new multiword names joined by hyphen, underscore, camelCase, or PascalCase.
- Framework-required filenames are allowed, for example `page.tsx`, `layout.tsx`, `loading.tsx`, `route.ts`, `__init__.py`, and migration filenames.
- Conventional test filenames are allowed, for example `test_user.py`, `user.test.ts`, `user.test.tsx`, and `page.test.tsx`.
- Conventional test tier directories `unit`, `integration`, and `e2e` are allowed.
- Existing public routes, database migrations, generated files, dependency folders, and third-party conventions are exempt unless the task explicitly renames them.
- If a concept needs several words, place code in an existing appropriate single-word directory and use clear symbol names inside the file.

## Architecture

- Prefer deep modules at stable boundaries: small typed domain interfaces that hide non-trivial implementation.
- Avoid shallow wrappers that only rename, forward, re-export, or add indirection without owning an invariant, policy, type boundary, or useful abstraction.
- Public APIs should express domain operations and invariants, not implementation steps.
- Keep entry points thin. Put business rules, persistence details, external SDK details, fetch details, and cache keys behind project-owned boundaries.
- SOLID is a maintenance constraint, not a reason for speculative abstraction. Do not add layers, factories, registries, event buses, or plugin systems unless the task or existing project pattern justifies them.
- Deep modules are not god modules. Split code when responsibilities, dependencies, reasons to change, or test setup become unrelated.

## Error Handling

- Do not add `try` blocks merely to make a bug disappear.
- Keep each `try` block as narrow as possible and catch the most specific error type available.
- Do not use bare `except`, catch `BaseException`, use empty `catch` blocks, or silently ignore errors.
- Avoid broad `except Exception` or broad `catch` unless it is at an application boundary and returns or raises a structured error.
- Do not return `None`, an empty collection, a default object, or a success response after an unexpected error unless that fallback is an explicit documented contract.
- Preserve causes when translating errors, for example `raise NewError(...) from exc` in Python.
- Tests must not hide assertion failures inside `try` blocks. Use `pytest.raises` or `await expect(...).rejects`.

## Backend

- Backend code lives under `backend/`.
- Python imports must be at module top, after the module docstring and `from __future__` imports.
- Do not add imports inside functions, methods, or branches except for a documented cycle, optional dependency, or cold-path performance reason.
- Keep each backend source file at or below 800 lines.
- Use pytest for tests, Ruff for formatting and lint-compatible style, and Pyright for backend type checking.
- Backend changes must not leave Pyright errors or warnings in touched code.
- Type hints must describe real values. Do not silence type issues with incorrect annotations, unnecessary casts, or broad `Any`.
- Prefer explicit Pydantic models, dataclasses, typed dicts, protocols, or narrow dictionaries over unstructured `dict[str, Any]` at boundaries.
- Use async all the way through async request, service, repository, and database paths.
- Do not call blocking I/O, `time.sleep()`, or `asyncio.run()` from async application code.
- Do not leave fire-and-forget tasks unmanaged. Background work needs ownership, error logging, cancellation behavior, and lifecycle boundaries.
- FastAPI route handlers should stay thin. Put business rules in services and persistence logic in repositories or the existing project boundary.
- Use explicit request and response models for API boundaries.
- Validate external input at the boundary before it reaches business logic.
- Do not leak ORM objects, internal exceptions, stack traces, secrets, or implementation details in public API responses.
- Use SQLAlchemy patterns already present in the project, especially around `AsyncSession`, relationships, eager loading, and transaction ownership.
- Keep transaction ownership explicit. Helpers should not call `commit()` unless their contract clearly owns the transaction.
- Prefer `flush()` when code needs generated IDs inside an existing transaction.
- Avoid raw SQL string interpolation. Use SQLAlchemy expressions or bound parameters.
- Schema changes require an Alembic migration unless the user explicitly requests implementation-only work.
- Do not include destructive or data-losing migrations unless the task explicitly asks for them and the behavior is documented.

### Backend Tests

Backend tests live under `backend/tests/` and are split by tier:

```text
backend/tests/unit/
backend/tests/integration/
backend/tests/e2e/
```

Mirror implementation paths when a test targets a source module:

```text
backend/<relative/path>/a.py
backend/tests/unit/<relative/path>/test_a.py
backend/tests/integration/<relative/path>/test_a.py
backend/tests/e2e/<relative/path>/test_a.py
```

Unit tests must isolate one module or small behavior. Integration tests validate real internal collaboration. E2E tests validate user-observable behavior through the application boundary. Bug fixes should include the narrowest test that would have failed before the fix.

### Backend Verification

Run the narrowest useful verification, then broaden when shared behavior changes:

```bash
cd backend && ruff format .
cd backend && ruff check .
cd backend && pyright
cd backend && pytest
```

For targeted tests, prefer:

```bash
cd backend && pytest path/to/test_file.py
```

## Frontend

- The primary frontend lives under `frontend/`.
- Use the Next.js, React, TypeScript, Tailwind, and Vitest stack already configured in `frontend/package.json`.
- Do not downgrade Next.js, React, TypeScript, or related framework packages unless the user explicitly asks.
- Keep each frontend source file at or below 900 lines.
- Keep React components focused. Extract reusable logic into existing `components`, `features`, `hooks`, `libs`, or `types` boundaries instead of growing large files.
- Use TypeScript strict types. Do not add explicit `any`, `as any`, `Record<string, any>`, unsafe double assertions, or `@ts-ignore`.
- Use `unknown` for untrusted external data and narrow it before use.
- Avoid non-null assertions. Prefer guards, early returns, invariant checks, or more accurate types.
- Keep server components server-side by default. Add `use client` only when client-only React features or browser APIs are genuinely needed.
- Do not access `window`, `document`, `localStorage`, cookies, or other browser-only APIs from server components or shared module scope.
- Do not duplicate backend API contract types manually when shared or generated types already exist.
- Every async UI state that can fail should have intentional loading, empty, and error behavior.
- Preserve accessibility with semantic HTML, form labels, keyboard-reachable interactions, useful alt text, and ARIA only when native semantics are insufficient.
- Use Tailwind and existing class composition utilities. Avoid one-off styling systems unless the task targets styling infrastructure.
- Do not edit `.next/`, `dist/`, `node_modules/`, coverage output, or generated build output.

### Frontend Tests

Frontend tests live under `frontend/tests/` and are split by tier:

```text
frontend/tests/unit/
frontend/tests/integration/
frontend/tests/e2e/
```

Mirror implementation paths when a test targets a source file:

```text
frontend/<relative/path>/a.ts
frontend/<relative/path>/a.tsx
frontend/tests/unit/<relative/path>/a.test.ts
frontend/tests/unit/<relative/path>/a.test.tsx
frontend/tests/integration/<relative/path>/a.test.ts
frontend/tests/integration/<relative/path>/a.test.tsx
frontend/tests/e2e/<relative/path>/a.test.ts
frontend/tests/e2e/<relative/path>/a.test.tsx
```

Unit tests isolate pure functions, hooks, components, or small modules. Integration tests validate collaboration across components, hooks, providers, routing, forms, and API clients. E2E tests validate user-observable flows through a real route or browser-like boundary. Do not introduce a new E2E framework unless the user explicitly asks or the repository already has it configured.

### Frontend Verification

Run the narrowest useful verification, then broaden when shared behavior changes:

```bash
cd frontend && pnpm lint
cd frontend && pnpm type-check
cd frontend && pnpm test
cd frontend && pnpm build
```

For targeted tests, prefer:

```bash
cd frontend && pnpm vitest run path/to/test_file.test.tsx
```

## Configuration, Dependencies, Security

- Do not hardcode secrets, tokens, passwords, private keys, account IDs, or environment-specific credentials.
- Use existing configuration loading and validation patterns.
- Keep `.env.example` and sample environment files free of real secrets.
- Do not add a runtime dependency when the standard library, existing dependency, or small local helper is sufficient.
- When a dependency change is necessary, update the appropriate lockfile and report why the dependency was needed.
- Keep backend and frontend contracts synchronized when API paths, payloads, validation, authentication, authorization, or error formats change.
- Enforce authentication and authorization at the backend boundary for protected resources.
- Do not trust client-provided identity, role, ownership, price, status, or permission fields.
- Validate and normalize external input before persistence or sensitive operations.
- Do not log secrets, credentials, session tokens, authorization headers, personal data, or large request bodies.
- Avoid SQL injection, command injection, path traversal, SSRF, XSS, open redirects, and unsafe deserialization.

## Documentation And Specs

- Keep specifications consistent with the current implementation baseline.
- Mark future phases clearly as future work.
- Do not mix first-phase requirements with later-phase ambitions in the same acceptance criteria.
- When replacing specs, delete superseded files only when the replacement preserves the original intent and clearly states what it replaces.
- Update relevant README, API notes, environment examples, or developer docs when behavior, setup, commands, or contracts change.

## Completion Expectations

- Before reporting completion, check the relevant git diff and verify no unrelated files were changed.
- Report what changed, what was verified, and any verification intentionally skipped.
- Do not claim a tool, test, type check, or build passed unless it was actually run and the output was checked.
- Mention known risks, follow-up work, or repository assumptions when they affect the result.
