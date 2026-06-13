# Module Standard

## Scope

Use this standard when creating or changing services, repositories, adapters, API clients, hooks, feature boundaries, shared contracts, or substantial component boundaries.

## Core Rule

Prefer deep modules: expose a small, typed, domain-oriented interface that hides non-trivial implementation. Avoid shallow modules that only rename, forward, re-export, or wrap one call without owning an invariant, policy, type boundary, or meaningful abstraction.

Deep modules reduce cognitive load because callers learn one stable interface instead of many implementation steps. A deep module can contain real complexity, but the complexity should be local, tested, and hidden behind a clear contract.

## Design Method

### 1. Find The Invariant Owner

Before writing code, identify who owns the rule being protected.

Examples:

- Email uniqueness belongs in the user registration service/repository boundary, not every route and form.
- Authorization belongs at the backend policy/service/API boundary, not only in frontend components.
- API response parsing belongs in the frontend API client, not every component.
- Form state transitions belong in a hook or reducer, not scattered event handlers.

Bug fixes should strengthen the owning module and add tests there. Do not spread defensive checks across unrelated callers unless each caller truly owns a separate invariant.

### 2. Design The Public Interface First

The public interface should describe the business operation, not internal steps.

Prefer:

```python
class RegisterUserCommand(BaseModel):
    email: EmailStr
    password: str
    display_name: str | None = None

class UserService:
    async def register(self, command: RegisterUserCommand, actor: Actor) -> UserRead:
        ...
```

Avoid:

```python
async def create_user(session, payload, commit, send_email, skip_validation):
    ...
```

Prefer:

```ts
export type UpdateUserCommand = {
  id: string;
  name: string;
  email: string;
};

export async function updateUser(command: UpdateUserCommand): Promise<UserView> {
  ...
}
```

Avoid repeating raw `fetch`, URL construction, JSON parsing, and error mapping in components.

### 3. Hide Implementation Details

Backend modules should hide:

- SQLAlchemy query details;
- transaction, flush, and commit details;
- authorization policy checks;
- ORM-to-response mapping;
- password hashing, token generation, and sensitive transformations;
- external SDK and HTTP client details;
- expected database error translation.

Frontend modules should hide:

- raw `fetch` details;
- route and query-string construction;
- JSON parsing and runtime narrowing;
- DTO-to-view-model mapping;
- cache keys and mutation internals;
- browser API details;
- loading, empty, error, and stale-response handling when those states are part of the abstraction.

### 4. Keep Entry Points Thin

FastAPI routes should mostly:

- accept validated request models;
- get dependencies;
- call a service or application use case;
- return response models;
- map expected domain errors through the existing error pattern.

Routes should not own business rules, SQLAlchemy queries, transaction strategy, or repeated error mapping.

Next.js pages and React components should mostly:

- read route params, props, or UI input;
- call hooks, API clients, or feature actions;
- render intentional UI states.

Components should not scatter API paths, response parsing, permission rules, cache keys, or complex state machines.

### 5. Test The Owning Boundary

Add the narrowest test that proves the owning module enforces the invariant:

- pure logic or mapper: unit test;
- service plus repository or API route plus dependencies: integration test;
- user-visible HTTP or browser flow: E2E test;
- hook/component state coordination: frontend integration test.

## SOLID Compatibility

Use SOLID as a practical constraint, not as a reason for speculative abstraction.

- Single Responsibility: one main reason to change per module, class, hook, or component.
- Open/Closed: extend through existing extension points or small collaborators when available.
- Liskov: implementations of the same protocol or component contract must keep behavior compatible.
- Interface Segregation: callers should not depend on props, fields, or methods they do not use.
- Dependency Inversion: domain logic should depend on project-owned abstractions at unstable boundaries, not directly on SDKs, browser APIs, HTTP clients, or database sessions unless that is the local established pattern.

Do not add interfaces, factories, registries, event buses, or plugin systems unless the task or existing codebase clearly needs them.

## Shallow Module Smells

A module is likely too shallow when it:

- only forwards parameters to another function;
- renames a third-party API without hiding policy or type details;
- exports catch-all option bags that leak internal switches;
- adds a wrapper that must change whenever its dependency changes;
- forces callers to understand transactions, SQL, cache keys, fetch mechanics, or SDK quirks;
- has tests that only assert the wrapper called another wrapper.

Delete the shallow layer, deepen it by owning a real invariant, or move the logic to the existing owner.

## God Module Smells

A module is too broad when it:

- has multiple unrelated reasons to change;
- depends on unrelated systems;
- needs large unrelated fixture setup;
- mixes HTTP, persistence, rendering, policy, and third-party concerns in one place;
- forces every change to touch the same large file.

Split by invariant, dependency direction, public boundary, or test setup. Do not split merely by tiny mechanical steps.

## Review Checklist

- Does the public API express a domain operation rather than implementation steps?
- Is the interface smaller and more stable than the implementation?
- Are transactions, SQLAlchemy details, fetch details, cache keys, env access, browser APIs, and SDKs hidden behind project-owned boundaries?
- Does the module own a clear invariant or policy?
- Did a bug fix strengthen the owning module instead of adding defensive checks everywhere?
- Is the module deep without becoming a god module?
- Are tests placed at the boundary that owns the behavior?
