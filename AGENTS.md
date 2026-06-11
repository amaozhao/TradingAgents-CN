# Project Agent Instructions

These instructions apply to the whole repository unless a deeper `AGENTS.md`
overrides them.

## General

- Do not commit or push changes unless the user explicitly asks for it in the current task.
- Keep changes small, reviewable, and scoped to the user's request.
- Prefer existing project patterns over new abstractions.
- Do not edit generated, vendored, cache, runtime, log, or dependency output unless the task explicitly targets them.
- Treat existing naming violations as legacy. New or renamed project-owned source files and directories must follow the naming rules below.

## Naming

- Project-owned file and directory names must be a single real word.
- Use lowercase ASCII words by default.
- Do not create fake compound words such as `loaddata`, `runagent`, `fetchreport`, or similar verb+noun concatenations.
- Avoid multiword names joined by hyphen, underscore, camelCase, or PascalCase for new files/directories.
- Framework-required filenames are allowed, for example `page.tsx`, `layout.tsx`, `loading.tsx`, `route.ts`, `__init__.py`, and migration filenames.
- Existing public routes, database migration names, generated files, dependency folders, and third-party conventions are exempt unless the task is explicitly to rename them.
- If a concept needs several words, prefer placing code inside an existing appropriate single-word directory and naming symbols clearly inside the file.

## Backend

- Backend code lives under `backend/`.
- Python imports must be at module top, after the module docstring and `from __future__` imports.
- Do not add imports inside functions, methods, or branches except for a documented cycle, optional dependency, or cold-path performance reason.
- Keep each backend source file at or below 800 lines.
- Use pytest for tests.
- Use Ruff for formatting and lint-compatible style.
- Use Pyright for backend type checking.
- Backend changes must not leave Pyright errors or warnings in touched code.
- Type hints must describe real values; do not silence type issues with incorrect annotations or unnecessary casts.
- Prefer explicit Pydantic models, dataclasses, typed dicts, or narrow dictionaries over unstructured `dict[str, Any]` when data crosses module boundaries.
- Do not swallow errors with broad `except Exception` blocks. If broad handling is unavoidable at a boundary, log or return a structured error and keep the protected block small.

### Backend Verification

Run the narrowest useful verification for the change, then broaden when the change affects shared behavior.

Common commands:

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
- Use the current stable Next.js and React stack already configured in `frontend/package.json`.
- Do not downgrade Next.js, React, TypeScript, or related framework packages unless the user explicitly asks.
- Frontend file and directory naming follows the same single-real-word rule as backend code, with Next.js framework filenames exempt.
- Keep each frontend source file at or below 900 lines.
- Keep React components focused. Extract reusable logic into existing `components`, `features`, `hooks`, `libs`, or `types` boundaries instead of growing large files.
- Use TypeScript with strict types. Avoid `any` unless the boundary is genuinely untyped and the value is narrowed immediately.
- Do not edit `.next/`, `dist/`, `node_modules/`, or generated build output.

### Frontend Verification

Run the narrowest useful verification for the change, then broaden when the change affects shared behavior.

Common commands:

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

## Documentation And Specs

- Keep specifications consistent with the current implementation baseline.
- Mark future phases clearly as future work.
- Do not mix first-phase requirements with later-phase ambitions in the same acceptance criteria.
- When replacing specs, delete superseded files only when the replacement preserves the original intent and clearly states what it replaces.

## Completion Expectations

- Before reporting completion, check the relevant git diff and verify no unrelated files were changed.
- Report what changed, what was verified, and any verification that was intentionally skipped.
- Do not claim a tool, test, type check, or build passed unless it was actually run and the output was checked.
