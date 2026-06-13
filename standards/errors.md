# Error Standard

## Scope

Use this standard when changing error handling, `try`/`except`/`catch`, fallback behavior, retries, logging, exception mapping, or error tests.

## Core Rules

- Do not add `try` blocks merely to make a bug disappear.
- Fix the invariant, validation, dependency, or caller contract when that is the real issue.
- Keep protected blocks narrow.
- Catch the most specific expected error type.
- Do not silently ignore errors.
- Do not convert unexpected failures into successful results.
- Preserve original causes when translating errors.

## Expected vs Unexpected Failures

Expected failures are part of the domain or boundary contract, such as:

- validation failure;
- authentication failure;
- authorization denial;
- not found;
- uniqueness conflict;
- external service timeout at a boundary with a retry/fallback policy.

Unexpected failures are bugs or infrastructure faults, such as:

- impossible state;
- missing required config;
- programmer error;
- malformed internal data;
- unhandled database or network failure.

Expected failures should be translated into structured domain, API, or UI errors. Unexpected failures should be logged at an appropriate boundary and allowed to fail visibly through the existing error mechanism.

## Python Rules

Good pattern:

```python
try:
    await repository.insert_user(command)
except UniqueViolationError as exc:
    raise EmailAlreadyExists(command.email) from exc
```

Bad pattern:

```python
try:
    ...
except Exception:
    return None
```

Rules:

- Do not use bare `except`.
- Do not catch `BaseException`, `KeyboardInterrupt`, or `SystemExit`.
- Avoid broad `except Exception`. If unavoidable at an application boundary, keep the protected block small, log useful context, and return or raise a structured error.
- Use `raise ... from exc` when translating exceptions.
- Use `finally` only for cleanup, and do not let cleanup suppress the original error.
- Do not use exceptions for ordinary control flow when a clear conditional is available.

## FastAPI Mapping

- Route handlers should map expected client-facing failures through `HTTPException` or the existing error response model.
- Prefer centralized exception handlers when the project already uses them.
- Do not expose stack traces, ORM exceptions, secrets, or internal implementation details in public responses.
- Do not turn unexpected server failures into `200` responses, empty payloads, or silent no-ops.

## SQLAlchemy Errors

- Catch database errors narrowly, such as constraint violations or missing rows.
- Translate persistence errors at repository, service, or API boundaries according to existing project patterns.
- Keep rollback logic in the transaction/session owner.
- Do not scatter rollback calls through unrelated helpers.

## TypeScript Rules

`catch` values should be treated as `unknown`:

```ts
try {
  return await updateUser(command);
} catch (error: unknown) {
  if (error instanceof ApiError) {
    return { status: "failed", message: error.message };
  }
  throw error;
}
```

Rules:

- Do not read properties from a caught value until it is narrowed.
- Do not use empty `catch` blocks.
- Do not hide failed API calls by returning empty arrays, default objects, or success states unless that is an explicit contract.
- Keep error handling at the boundary: API client, form submit handler, route action, error boundary, or controlled effect.
- Do not wrap React render logic in broad `try` blocks. Use route, segment, or component error boundaries when appropriate.

## Fallbacks

Fallbacks are allowed only when they are explicit domain behavior. A fallback must answer:

- what failure it handles;
- why continuing is safe;
- what the caller or user can observe;
- how the failure is logged or surfaced if needed.

Do not use fallbacks to conceal broken contracts, missing configuration, invalid state, or failed persistence.

## Retries

Use retries only for transient failures and only at the boundary that owns the external call. Retries should have limits, backoff when appropriate, and cancellation/timeout behavior.

Do not retry validation errors, authorization errors, deterministic bugs, or non-idempotent operations unless the operation is explicitly safe to retry.

## Logging

Log enough context to debug without exposing secrets or personal data. Include stable identifiers when safe, not entire request bodies or tokens.

## Testing Errors

- Use `pytest.raises` for expected Python exceptions.
- Use `await expect(...).rejects` or equivalent for expected TypeScript promise failures.
- Test expected error mapping at the owning boundary.
- Test that unexpected failures are not silently converted into success.

## Review Checklist

- Is the `try` block narrow?
- Is the caught error specific?
- Are unexpected errors allowed to fail through the proper boundary?
- Is fallback behavior explicitly part of the contract?
- Are original causes preserved when translated?
- Are secrets and personal data excluded from logs and error responses?
- Do tests prove the expected error behavior?
