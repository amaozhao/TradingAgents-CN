# Testing Standard

## Scope

Use this standard when adding or changing tests, fixtures, mocks, test data, test layout, or verification commands.

## Core Rules

- Tests must be deterministic, isolated, and meaningful.
- Add the narrowest regression test that would have failed before a bug fix.
- Do not hide failures with broad `try` blocks, arbitrary sleeps, broad mocks, or snapshots that do not assert behavior.
- Follow existing project test tooling: pytest for backend and Vitest or the configured equivalent for frontend.
- Do not introduce a new E2E framework unless the repository already uses it or the user explicitly asks.

## Directory Layout

Backend tests live under:

```text
backend/tests/unit/
backend/tests/integration/
backend/tests/e2e/
```

Frontend tests live under:

```text
frontend/tests/unit/
frontend/tests/integration/
frontend/tests/e2e/
```

Tier directories `unit`, `integration`, and `e2e` are allowed naming exceptions.

## Mirrored Paths

When a test targets a specific backend source module, mirror the implementation path:

```text
backend/<relative/path>/a.py
backend/tests/unit/<relative/path>/test_a.py
backend/tests/integration/<relative/path>/test_a.py
backend/tests/e2e/<relative/path>/test_a.py
```

When a test targets a specific frontend source file, mirror the implementation path:

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

When no single source file owns the behavior, place the test under the nearest mirrored public boundary, route, feature, or application path.

## Unit Tests

Unit tests validate one module, function, class, hook, component, mapper, reducer, or small service behavior in isolation.

Backend unit tests must not require:

- a real database;
- a running application server;
- network calls;
- external services;
- filesystem state outside `tmp_path`.

Frontend unit tests should mock or fake network calls, router state, storage, time, and browser globals unless those dependencies are the behavior under test.

## Integration Tests

Integration tests validate collaboration across real internal boundaries.

Backend examples:

- service plus repository;
- API route plus dependency graph;
- SQLAlchemy queries against a test database;
- transaction behavior.

Frontend examples:

- component plus hook plus provider;
- form plus validation plus API client boundary;
- route behavior with configured router utilities;
- state transitions that require multiple components.

Integration tests should use isolated test resources and must never point at development, staging, or production services.

## E2E Tests

E2E tests validate user-observable behavior through the application boundary. Prefer real HTTP or the configured browser-like runner. Mock only external systems that are unsafe, paid, slow, flaky, or unavailable in test environments.

Do not use E2E tests as the only coverage for logic that can be tested closer to the owning module.

## Fixtures And Test Data

- Put shared pytest fixtures in the nearest appropriate `conftest.py`.
- Use wider fixtures only when genuinely shared across many tests.
- Prefer explicit builders or factories over large implicit fixture graphs.
- Keep fixture names clear about domain meaning, not implementation setup.
- Do not import helpers from one test tier into another unless the helper is tier-neutral and lives in shared support code.
- Test data should be realistic enough to trigger validation, authorization, and serialization behavior.
- Do not use production-like secrets, real personal data, or real third-party credentials in tests.
- Control randomness and time through injected clocks, factories, monkeypatching, or fake timers.

## Mocking Rules

Mock at the unstable boundary, not at every internal call.

Good mock boundaries:

- third-party HTTP services;
- email/SMS/payment providers;
- time and randomness;
- browser storage and navigation;
- unavailable or unsafe external resources.

Avoid mocks that:

- duplicate implementation details;
- assert a chain of internal calls instead of observable behavior;
- hide broken contracts between real project modules;
- make tests pass while production behavior is untested.

## Async Tests

- Use the project's configured async test support.
- Do not use arbitrary sleeps.
- Prefer explicit awaits, deterministic synchronization, polling helpers with timeouts, or test client utilities.
- Clean up tasks, sessions, connections, and temporary resources.

## Database Tests

- Use isolated test databases, transactions, schemas, or fixtures according to the existing project pattern.
- Keep transaction ownership clear in tests as well as production code.
- Roll back or recreate state deterministically.
- Test constraints and important query behavior at integration level when they cannot be proven with unit tests.

## Frontend Query Rules

- Prefer user-visible queries and interactions over implementation details.
- Test what the user can observe: text, roles, labels, form behavior, navigation, and error states.
- Avoid snapshots as the primary behavior assertion.
- Use snapshots only for stable, intentionally reviewed output.

## Verification Strategy

Run the narrowest useful command first. Broaden when a change touches shared behavior, public contracts, test infrastructure, or framework configuration.

Backend common commands:

```bash
cd backend && ruff format .
cd backend && ruff check .
cd backend && pyright
cd backend && pytest
```

Frontend common commands:

```bash
cd frontend && pnpm lint
cd frontend && pnpm type-check
cd frontend && pnpm test
cd frontend && pnpm build
```

Targeted examples:

```bash
cd backend && pytest path/to/test_file.py
cd frontend && pnpm vitest run path/to/test_file.test.tsx
```

## Review Checklist

- Is the test in the correct tier?
- Does the path mirror the owning source path when applicable?
- Would the regression test fail before the fix?
- Are mocks placed at unstable boundaries rather than internal implementation steps?
- Are fixtures explicit, local, and deterministic?
- Are async operations awaited deterministically?
- Did verification run at the narrowest useful scope and broaden when necessary?
