# Frontend Standard

## Scope

Use this standard when changing Next.js routes, React components, hooks, forms, UI state, API clients, Tailwind styling, accessibility, or frontend performance.

## Core Rules

- Keep server components server-side by default.
- Add `use client` only when browser APIs, effects, state, event handlers, refs, or client-only libraries are genuinely needed.
- Keep components focused and move reusable logic into existing `components`, `features`, `hooks`, `libs`, or `types` boundaries.
- Do not scatter raw `fetch`, backend contract assumptions, cache keys, or complex state machines across components.
- Use TypeScript strict types and follow `standards/typing.md`.

## Component Boundaries

Components should primarily render UI from props and user-visible state. Move non-render concerns to better owners:

- API calls: API client, action, or hook;
- validation schemas: form/domain boundary;
- state machines: hook or reducer;
- mapping DTOs: API client or mapper;
- permissions: backend first, frontend only for UX gating.

Avoid props that leak internals, such as multiple booleans that can combine into impossible states. Prefer discriminated unions for mutually exclusive UI states.

## Server And Client Components

Server components may fetch server-safe data and render non-interactive UI. Client components may use state, effects, browser APIs, and event handlers.

Rules:

- Do not access `window`, `document`, `localStorage`, or browser-only APIs from server components or shared module scope.
- Do not move a large subtree to client rendering just to support a small interactive child.
- Do not pass non-serializable values from server to client components.
- Keep server-only secrets and privileged data out of client bundles.

## Data Fetching And API Clients

- Centralize endpoint paths, methods, request typing, response narrowing, and error mapping.
- Components should call a project-owned API client, server action, or feature hook rather than raw endpoints.
- Treat API responses as untrusted unless generated/shared types and runtime behavior make the trust boundary explicit.
- Handle stale async work when inputs change or components unmount.
- Preserve existing caching and mutation patterns instead of adding new state libraries.

## Hooks

Hooks can be deep modules when they expose a small UI-oriented interface and hide complex state, effects, cache, or browser details.

A hook should:

- have a clear purpose;
- clean up effects;
- avoid stale closures;
- expose typed state and actions;
- avoid owning unrelated UI concerns.

Do not build god hooks that mix API calls, form validation, routing, permissions, layout, and unrelated state.

## Forms

- Use existing form and validation patterns.
- Keep field-level and form-level errors explicit.
- Disable or guard duplicate submissions when needed.
- Preserve user input after validation failures unless clearing is intentional.
- Make validation messages accessible to assistive technologies.
- Do not trust frontend validation as a security boundary.

## UI State

Every async UI that can fail should have intentional loading, empty, success, and error behavior. Use discriminated unions when multiple booleans can create illegal states.

Example states:

```ts
type LoadState<T> =
  | { status: "loading" }
  | { status: "empty" }
  | { status: "ready"; data: T }
  | { status: "failed"; message: string };
```

## Tailwind And Styling

- Use Tailwind and existing class composition utilities.
- Prefer reusable variants or existing components for repeated patterns.
- Do not introduce a parallel styling system unless the task explicitly targets styling infrastructure.
- Keep responsive behavior intentional.
- Avoid inline styles unless values are dynamic and cannot reasonably be represented through existing utilities.
- Do not hardcode one-off colors or spacing when the project has tokens or established classes.

## Accessibility

- Use semantic HTML first.
- Associate labels with form controls.
- Ensure interactive elements are keyboard reachable.
- Preserve visible focus states.
- Use useful `alt` text for meaningful images and empty `alt` for decorative images.
- Use ARIA only when native semantics are insufficient, and keep ARIA state synchronized.
- Make dialogs, menus, and popovers manage focus and dismissal intentionally.

## Frontend Performance

- Avoid unnecessary client-side rendering for data that can be rendered server-side.
- Avoid large dependencies for small UI behavior.
- Use dynamic imports only when they reduce meaningful initial cost and do not harm UX.
- Memoize only when there is a measured or clear render problem; do not scatter `memo`, `useMemo`, or `useCallback` mechanically.
- Optimize images and assets through existing Next.js/project patterns.

## Tests

- Unit test pure UI logic, reducers, mappers, and focused components.
- Integration test components with hooks, providers, routing, forms, and API client boundaries.
- Prefer user-visible queries over implementation details.
- Cover loading, empty, error, and success states for async UI.
- Avoid snapshots as the primary behavior assertion.

## Review Checklist

- Is `use client` limited to the smallest necessary boundary?
- Are raw API details hidden behind an API client, action, or hook?
- Are UI states explicit and impossible states avoided?
- Are forms accessible and resilient to errors?
- Does styling follow existing Tailwind/component patterns?
- Are keyboard and screen-reader basics preserved?
- Are performance optimizations justified rather than speculative?
