# Typing Standard

## Scope

Use this standard when changing TypeScript types, Python type hints, schemas, DTOs, API contracts, React props, untrusted data parsing, or boundary models.

## Shared Principles

- Types must describe real runtime values.
- Do not lie to the type checker to make an error disappear.
- Treat external data as untrusted until validated or narrowed.
- Prefer explicit boundary models over loose dictionaries, catch-all objects, or broad option bags.
- Optionality must be meaningful: distinguish missing, `null`, empty string, empty array, and default value.
- Tests should not bypass type safety just to make setup shorter.

## TypeScript Rules

### Forbidden Patterns

Do not add:

```ts
any
as any
Array<any>
Promise<any>
Record<string, any>
any[]
// @ts-ignore
value as unknown as Target
```

`@ts-expect-error` is allowed only for intentional negative tests or unavoidable third-party type gaps, and it must include a short reason.

Avoid non-null assertions:

```ts
value!
```

Prefer guards, early returns, assertions with real runtime checks, or more accurate types.

### `unknown` And Narrowing

Use `unknown` at untrusted boundaries, then narrow:

- API responses;
- `catch` values;
- `JSON.parse`;
- localStorage/sessionStorage values;
- third-party SDK payloads;
- URL query parameters when parsed manually.

Narrow with runtime checks, type guards, schema validators already used by the project, discriminated unions, or explicit mappers.

### API Types

- Request and response types must be explicit at API client boundaries.
- Do not scatter handwritten response types if shared or generated contract types already exist.
- Do not claim an API response is a type unless it was generated/shared, validated, or narrowed.
- Map transport DTOs to view models at a stable boundary when UI shape differs from API shape.

### React Types

- Props should express component intent, not internal implementation switches.
- Avoid boolean prop combinations that create illegal UI states. Prefer discriminated unions for mutually exclusive states.
- Hook return types should be explicit when the inferred type is too wide, unstable, or part of a public boundary.
- Event handlers should use concrete React event types when needed.

### Config And Lookup Tables

Use precise literal types when useful:

```ts
const statuses = ["draft", "published"] as const;
type Status = (typeof statuses)[number];
```

Avoid broad `string` when only a known finite set is valid.

## Python Rules

### Avoid `Any`

Do not add broad `Any` or `dict[str, Any]` unless the value truly crosses an untyped external boundary and is narrowed immediately.

Prefer:

- Pydantic models for API and validation boundaries;
- dataclasses for internal structured values;
- `TypedDict` for dictionary-shaped payloads;
- `Protocol` for behavior-oriented interfaces;
- narrow dictionaries such as `dict[str, str]` when the value shape is genuinely uniform.

### Real Models At Boundaries

Use explicit models when data crosses:

- FastAPI request/response boundaries;
- service boundaries;
- repository return boundaries;
- background job boundaries;
- external API adapters;
- serialization/deserialization boundaries.

Do not leak ORM models as public API response types unless the existing project pattern explicitly does so.

### Optionality

Use `T | None` only when `None` is a real value the caller must handle. Do not use optional types to avoid initialization or validation.

### Casts And Ignores

Avoid `cast()` and `# type: ignore`. If unavoidable, keep the scope tiny and explain the reason. Do not use them to hide a real mismatch in API, ORM, or domain models.

### Protocols And Interfaces

Use `Protocol` or narrow interfaces only where they reduce coupling at a real boundary, such as external services or test fakes. Do not create protocols for every class mechanically.

### Async Types

Annotate async functions with their awaited return values, not coroutine internals. Do not hide mixed sync/async behavior behind inaccurate annotations.

## Cross-Language Contract Types

When backend and frontend share an API contract:

- keep backend Pydantic models and frontend TypeScript types synchronized;
- prefer generated or shared types when the project has that pattern;
- update frontend API clients when backend response shapes change;
- update tests on both sides when a contract change is observable.

## Test Typing

- Do not use `any`, broad `Any`, or unsafe casts in tests to bypass real contract requirements.
- Test fixtures should construct valid typed values unless the test intentionally covers invalid input.
- Negative type tests must be explicit about what type failure is expected.

## Review Checklist

- Did any new explicit `any`, `Any`, `as any`, unsafe cast, or ignore comment appear?
- Are untrusted values validated or narrowed before use?
- Are API request and response shapes explicit?
- Are React state and props precise enough to prevent illegal states?
- Are Python boundary values modeled with Pydantic, dataclasses, `TypedDict`, protocols, or narrow dictionaries?
- Does optionality reflect runtime truth?
- Are backend and frontend contract types synchronized?
