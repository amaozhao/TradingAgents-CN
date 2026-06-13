# Review Standard

This standard defines the final review workflow for code changes and the checklist to use when asked to review a change.

## Core Rule

Review the actual diff, verify relevant behavior, and report only what was truly changed and checked.

Do not claim a lint, type check, test, or build passed unless it was actually run and the output was checked.

## Review Workflow

### 1. Check Scope

Confirm the diff is limited to the user's request.

Look for:

- unrelated formatting;
- generated files;
- cache/runtime/build output;
- dependency output;
- accidental lockfile changes;
- unrelated refactors;
- changes outside the intended backend/frontend area.

### 2. Check Architecture

Apply `modules.md`.

Ask:

- Is the owning module responsible for the invariant?
- Did the change avoid shallow wrappers?
- Did the change avoid god modules?
- Are public interfaces typed and domain-oriented?
- Are infrastructure details hidden behind project-owned boundaries?

### 3. Check Types

Apply `typing.md`.

Ask:

- Did the change add `any` or `Any`?
- Did it add unsafe casts?
- Did it add `@ts-ignore` or broad `type: ignore`?
- Are request/response/schema types explicit?
- Are nullable values handled honestly?

### 4. Check Errors

Apply `errors.md`.

Ask:

- Did the change add broad `try`/`catch`/`except`?
- Are expected errors mapped at the correct boundary?
- Are unexpected errors allowed to surface?
- Are fallbacks explicit and safe?
- Are logs useful and redacted?

### 5. Check Contracts

Apply `contracts.md` when API behavior changes.

Ask:

- Did backend and frontend types change together?
- Are request/response schemas explicit?
- Are status codes correct?
- Are error formats stable?
- Are contract tests updated?

### 6. Check Database

Apply `database.md` when persistence changes.

Ask:

- Is transaction ownership clear?
- Are commits only at the owner boundary?
- Are migrations included for schema changes?
- Are tenant scopes preserved?
- Are query ordering and pagination stable?
- Are database tests updated?

### 7. Check Frontend

Apply `frontend.md` when UI changes.

Ask:

- Is the server/client boundary correct?
- Did the change avoid unnecessary `use client`?
- Are loading/error/empty states handled?
- Is the UI accessible?
- Does styling follow existing patterns?
- Are focused component/hook tests updated?

### 8. Check Security

Apply `security.md` for auth, tenant, secret, upload, redirect, webhook, or untrusted input changes.

Ask:

- Is backend authorization enforced?
- Is tenant isolation preserved?
- Are secrets protected?
- Is input validated?
- Are sensitive values redacted from logs/errors?

### 9. Check Operations And Performance

Apply `operations.md` and `performance.md` when relevant.

Ask:

- Were dependencies justified and lockfiles updated?
- Is configuration typed and validated?
- Are logs/metrics/traces useful and safe?
- Did the change introduce obvious latency, query, bundle, or payload problems?

### 10. Check Tests And Verification

Apply `testing.md`.

Ask:

- Are tests in the correct layer?
- Do test paths mirror source paths?
- Is there regression coverage for bug fixes?
- Were mocks placed at stable boundaries?
- Was the narrowest useful verification run?
- Should verification be broadened because shared behavior changed?

## Completion Report

Report completion in this structure when useful:

```text
Changed:
- ...

Verified:
- ...

Skipped:
- ... because ...

Notes:
- ...
```

Keep the report factual. Mention risks or assumptions rather than hiding them.

## Review Findings Format

When reviewing, prioritize correctness and safety issues first.

Use severity when helpful:

- Critical: security/data loss/build-breaking production risk.
- High: likely functional bug or broken contract.
- Medium: maintainability, test gap, type-safety gap, performance risk.
- Low: clarity or minor cleanup.

Each finding should include:

- file/location if available;
- problem;
- impact;
- recommended fix.

Do not invent issues. If the diff is unavailable or incomplete, state the limitation.

## Review Checklist

- Scope is limited.
- No generated/dependency/cache output changed accidentally.
- Architecture follows module boundaries.
- Types are honest and strict.
- Errors are not swallowed.
- Contracts are synchronized.
- Database ownership and migrations are correct.
- Frontend server/client/accessibility/state boundaries are correct.
- Security boundaries are enforced on backend.
- Dependencies/config/logging/performance risks are reviewed.
- Tests and verification match the change.
- Final report is truthful.
