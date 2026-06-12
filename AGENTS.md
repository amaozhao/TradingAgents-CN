# Project Agent Instructions

These instructions apply repo-wide unless a deeper `AGENTS.md` overrides them.

## Core Rules

- Do not commit or push unless the user explicitly asks in the current task.
- Keep changes small, scoped, and reviewable. Prefer existing project patterns over new abstractions.
- Inspect current implementation and configuration before changing architecture, dependencies, test layout, build tooling, or public contracts.
- Do not edit generated, vendored, cache, runtime, log, build, coverage, or dependency output unless the task targets it.
- Fix root causes. Do not hide bugs behind broad fallbacks, broad exception handling, weak types, or silent defaults.
- Avoid unrelated formatting churn; format only touched files unless asked for a larger cleanup.
- Keep specs, tests, implementation, and docs consistent.

## Naming

- New or renamed project-owned files and directories must be one real word, lowercase ASCII by default.
- Do not create fake compounds or multiword names joined by hyphen, underscore, camelCase, or PascalCase.
- Allowed exceptions: framework filenames such as `page.tsx`, `layout.tsx`, `loading.tsx`, `route.ts`, `__init__.py`; migration filenames; conventional test filenames; `unit`, `integration`, and `e2e` test tier directories; existing public routes, generated files, dependencies, and third-party conventions.
- For multiword concepts, prefer an existing appropriate single-word directory and clear symbol names inside the file.

## Architecture

- Prefer deep modules at stable boundaries: expose a small, typed, domain-oriented interface that hides non-trivial implementation.
- Public functions, classes, hooks, components, and services must add semantic value; avoid pass-through wrappers, re-export layers, and shallow modules that only rename or forward parameters.
- Design APIs around domain operations and invariants, not implementation steps. Hide transactions, SQLAlchemy queries, HTTP/fetch details, cache keys, env access, browser APIs, and third-party SDKs behind project-owned boundaries.
- Keep interfaces narrower than implementations: use explicit command/query models, props, or parameter objects only when they clarify the domain; avoid catch-all option bags and boolean flags that leak internals.
- When fixing bugs, strengthen the owning module's invariant and tests instead of spreading defensive checks across unrelated callers.
- Deep modules are not god modules. Split code when responsibilities, reasons to change, dependencies, or test setup become unrelated.
- Apply SOLID pragmatically. Do not add ceremony only to satisfy a pattern.
- Prefer simple, local, explicit code. Do not add interfaces, base classes, factories, registries, containers, event buses, or generic frameworks for one known implementation unless the project already uses that pattern or the task requires it.
- Keep modules, classes, functions, hooks, components, services, repositories, and routes focused on one primary responsibility. Split unrelated validation, authorization, orchestration, persistence, transport, rendering, formatting, and side effects.
- Extend through existing stable seams, small collaborators, validators, handlers, or components when variation exists; do not rewrite unrelated callers for a focused change.
- Implementations, wrappers, and adapters must preserve their contracts: accepted inputs, outputs, errors, async behavior, and side effects.
- Prefer narrow protocols, interfaces, props, hooks, service methods, repository methods, and API clients over god interfaces, large contexts, or catch-all option bags.
- Keep dependency direction explicit. Entry points call application logic; application logic calls infrastructure; lower layers must not import routes, pages, or UI.
- Avoid circular dependencies, hidden global state, mutable singletons, god services, catch-all utility files, and broad manager modules.
- Business and UI logic should not directly construct volatile external clients or depend on DB, HTTP, browser APIs, env, or third-party SDKs; use project-owned boundaries, injection, or existing framework dependency mechanisms.
- Share code only when the abstraction is stable or the move clarifies a real boundary. Do not perform broad architecture rewrites unless asked.

## Error Handling And `try`

- Use `try`/`catch` only around the expected failure boundary, with the smallest practical block.
- Catch the most specific error available. Do not use bare `except`, `BaseException`, `KeyboardInterrupt`, `SystemExit`, empty `catch`, empty callbacks, or `pass` to ignore errors.
- Avoid broad `except Exception` or catch-all handlers. If unavoidable at an application boundary, log useful context and return or raise a structured error.
- Do not return success, `None`, empty collections, or default objects after unexpected errors unless that fallback is an explicit documented contract.
- Preserve causes when translating errors, for example `raise NewError(...) from exc` in Python and retaining the original JS/TS error in logs.
- Use `finally` only for cleanup, and never let cleanup suppress the original failure.
- Tests must not hide assertion failures in `try`; use `pytest.raises` or `await expect(...).rejects`.

## Backend

- Backend code lives under `backend/`. Keep backend source files at or below 800 lines.
- Python imports must be at module top after docstring and `from __future__` imports; local imports require a documented cycle, optional dependency, or cold-path reason.
- Use Ruff, Pyright, and pytest. Touched backend code must not leave Pyright errors or warnings.
- Use precise real types: Pydantic models, dataclasses, `TypedDict`, `Protocol`, enums, literals, and narrow aliases. Avoid `Any`, incorrect optionality, unnecessary `cast`, `# type: ignore`, and loose dictionaries across module boundaries.
- Keep async paths async through request, service, repository, and DB layers. Do not use blocking I/O, `asyncio.run()`, manual event loops, unmanaged fire-and-forget tasks, or `time.sleep()` in async code.
- FastAPI routes should stay thin. Put business rules in services and persistence in repositories or the existing project boundary.
- Use explicit request/response models and validate external input at the boundary.
- Do not leak ORM objects, internal exceptions, stack traces, secrets, or implementation details in public API responses.
- Use existing exception mapping, `HTTPException`, or the existing error response model for expected failures. Never convert unexpected server errors into `200`, empty payloads, or silent no-ops.
- Follow existing SQLAlchemy `AsyncSession`, relationship, eager-loading, and transaction patterns.
- Keep transaction ownership explicit. Helpers should not `commit()` or `rollback()` unless they own the transaction. Use `flush()` for generated IDs inside an active transaction.
- Catch DB errors narrowly, avoid raw SQL interpolation, and avoid N+1 query patterns.
- Schema changes require a focused Alembic migration. Do not add destructive or data-losing migrations unless explicitly requested and documented.

## Backend Tests

Backend tests live under `backend/tests/{unit,integration,e2e}/` and mirror implementation paths:

```text
backend/<path>/a.py -> backend/tests/unit/<path>/test_a.py
backend/<path>/a.py -> backend/tests/integration/<path>/test_a.py
backend/<path>/a.py -> backend/tests/e2e/<path>/test_a.py
```

- Unit tests isolate one module, function, class, or small service; no real DB, network, external service, or filesystem state outside `tmp_path`.
- Integration tests validate real internal boundaries such as service plus repository, route plus dependencies, or SQLAlchemy plus test DB, using isolated test resources.
- E2E tests validate user-observable application boundaries, usually HTTP or the configured runner; avoid internal mocks except unsafe, slow, paid, flaky, or unavailable external services.
- If no single source module owns the behavior, place tests under the nearest mirrored public boundary or feature path.
- Shared fixtures belong in the nearest `conftest.py`; tier-neutral helpers may live in shared support code. Do not import helpers across tiers unless tier-neutral.
- Bug fixes need the narrowest regression test that would have failed before the fix. Add broader coverage when the bug crosses boundaries.
- Do not use arbitrary sleeps. Use deterministic synchronization, explicit awaits, polling with timeouts, or test client utilities. Configure pytest markers before use.

## Backend Verification

```bash
cd backend && ruff format .
cd backend && ruff check .
cd backend && pyright
cd backend && pytest
```

Targeted:

```bash
cd backend && pytest path/to/test_file.py
cd backend && pytest tests/unit
cd backend && pytest tests/integration
cd backend && pytest tests/e2e
```

## Frontend

- Primary frontend lives under `frontend/`. Keep frontend source files at or below 900 lines.
- Use the configured Next.js, React, TypeScript, Tailwind, and package manager setup. Do not downgrade framework packages unless asked.
- Keep components focused. Extract reusable logic into existing `components`, `features`, `hooks`, `libs`, or `types` boundaries.
- Do not edit `.next/`, `dist/`, `node_modules/`, coverage, or generated build output.
- Keep server components server-side by default. Add `use client` only for client React features or browser APIs.
- Do not access `window`, `document`, `localStorage`, or browser APIs from server components or shared module scope.
- Prefer existing data-fetching, caching, routing, mutation, styling, and class-composition patterns.
- Async UI that can fail needs intentional loading, empty, and error behavior.
- Preserve accessibility with semantic HTML, labels, keyboard access, useful alt text, and ARIA only when native semantics are insufficient.

## Frontend TypeScript

- Strict TypeScript is required. Do not introduce explicit or implicit `any`, `as any`, `Array<any>`, `Record<string, any>`, or generic escape hatches.
- Use `unknown` for untrusted or untyped values, then narrow with checks, type guards, schema validation, discriminated unions, or existing validators.
- Rare `any` is allowed only in the smallest documented adapter for unavoidable third-party, generated, or legacy boundaries; narrow it immediately.
- Do not use `@ts-ignore`. Use `@ts-expect-error` only for intentional negative tests or documented external typing defects.
- Avoid unsafe assertions, double assertions, non-null `!`, broad `object`/`Function`/`Record<string, unknown>`/`string` replacements, and weakened compiler options.
- Exported functions, hooks, API clients, context providers, shared utilities, and non-trivial component props need clear parameter and return types when inference is not obvious.
- Prefer domain types, interfaces, aliases, discriminated unions, and schema-derived, shared, or generated contract types.
- Validate or narrow runtime data from APIs, forms, storage, URL params, cookies, and third-party libraries before trusting it.
- Use `satisfies` for typed config or lookup tables when helpful, and `import type`/`export type` for type-only imports.
- Type React props, events, refs, and context values precisely. Do not mutate props, React state, cached data, or caller-owned objects unless mutation is the explicit contract.
- Verify types with `pnpm type-check`; do not add fake runtime tests to compensate for weak types.

## Frontend Tests

Frontend tests live under `frontend/tests/{unit,integration,e2e}/` and mirror implementation paths:

```text
frontend/<path>/a.ts(x) -> frontend/tests/unit/<path>/a.test.ts(x)
frontend/<path>/a.ts(x) -> frontend/tests/integration/<path>/a.test.ts(x)
frontend/<path>/a.ts(x) -> frontend/tests/e2e/<path>/a.test.ts(x)
```

- Unit tests isolate pure functions, hooks, components, or modules; mock network, router, time, storage, and browser globals when they are not the behavior under test.
- Integration tests validate collaboration across components, hooks, providers, routing, forms, and API clients with the existing Vitest and Testing Library setup or configured equivalent.
- E2E tests validate user-visible flows through a real route or browser-like boundary using the configured runner. Do not add a new E2E framework unless asked or already configured.
- If no source file owns the behavior, place tests under the nearest mirrored route, public component boundary, or feature path.
- Shared setup belongs in the existing setup file or nearest support module. Avoid broad global mocks when local mocks suffice.
- Prefer user-visible queries and interactions over implementation details. Snapshots are only for stable, intentionally reviewed output.
- Bug fixes need the narrowest regression test that would have failed before the fix. Add broader coverage when UI, routing, or API boundaries are crossed.

## Frontend Verification

```bash
cd frontend && pnpm lint
cd frontend && pnpm type-check
cd frontend && pnpm test
cd frontend && pnpm build
```

Targeted:

```bash
cd frontend && pnpm vitest run path/to/test_file.test.tsx
cd frontend && pnpm vitest run tests/unit
cd frontend && pnpm vitest run tests/integration
```

Run E2E only with the repository's existing configured command.

## Config, Dependencies, Security

- Do not hardcode secrets, tokens, passwords, private keys, account IDs, or environment-specific credentials. Keep sample env files secret-free.
- Use existing config loading and validation. Do not add a dependency when the standard library, existing dependency, or small local helper is sufficient. Update lockfiles and explain necessary dependency changes.
- Keep backend and frontend contracts synchronized: paths, payloads, validation, auth, and error formats.
- Backend authentication and authorization are authoritative. Do not trust client-provided identity, role, ownership, price, status, or permission fields.
- Validate and normalize external input before persistence or sensitive operations.
- Do not log secrets, credentials, session tokens, authorization headers, personal data, or large request bodies.
- Avoid SQL injection, command injection, path traversal, SSRF, XSS, open redirects, and unsafe deserialization. Use parameterized DB access and safe URL/path construction.

## Docs And Completion

- Keep specs aligned with implementation. Mark future phases as future work and do not mix phase-one requirements with later ambitions.
- Update relevant README, API notes, environment examples, or developer docs when behavior, setup, commands, or contracts change.
- Before reporting completion, inspect the relevant git diff and verify no unrelated files changed.
- Report what changed, what verification ran, what verification was skipped, and known risks or follow-up work.
- Never claim a tool, test, type check, or build passed unless it was actually run and checked.
