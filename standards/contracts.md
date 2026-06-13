# Contract Standard

## Scope

Use this standard when changing backend API routes, frontend API clients, request or response schemas, status codes, validation, authentication, authorization, pagination, filtering, sorting, or error response formats.

## Core Rules

- A contract change must update every affected boundary: backend models, route behavior, frontend API client, frontend types, tests, and documentation when applicable.
- Do not let components call raw endpoints directly when a project-owned API client or action should own the contract.
- Do not leak database, ORM, SDK, stack trace, or internal exception details through public contracts.
- Breaking changes must be intentional and documented in the task result.

## Contract Ownership

Backend owns:

- validation and authorization;
- status codes;
- public response shape;
- error format;
- persistence-to-response mapping.

Frontend owns:

- typed API client calls;
- narrowing untrusted responses when needed;
- transport DTO to view model mapping;
- user-facing error display.

Both sides must stay synchronized.

## Path And Method Rules

- Follow existing route naming and versioning patterns.
- Use HTTP methods according to behavior: `GET` for read, `POST` for create or action, `PATCH` for partial update, `PUT` for replacement, `DELETE` for deletion.
- Do not encode sensitive data in URLs.
- Keep route paths stable unless the task explicitly asks for a breaking change.

## Request Models

- Use explicit Pydantic request models on backend boundaries.
- Use explicit TypeScript command/request types on frontend API clients.
- Reject or ignore fields according to existing backend validation policy; do not trust client-provided role, ownership, price, status, or permission fields.
- Normalize and validate external input before persistence or sensitive operations.

## Response Models

- Use explicit backend response models.
- Return only fields the client should see.
- Avoid leaking ORM objects or internal enum values unless they are intentionally public.
- Keep response optionality meaningful and synchronized with frontend types.
- Map backend DTOs to frontend view models when the UI shape differs.

## Error Format

Use the project's existing error response format. If no pattern exists, prefer a stable structure with:

```json
{
  "code": "stable_error_code",
  "message": "Human-readable message",
  "details": {}
}
```

Rules:

- Use stable machine-readable codes for expected errors.
- Do not expose stack traces or internal exception names.
- Use field-level details for validation errors when useful.
- Keep frontend error handling centralized in the API client, action, or form boundary.

## Status Codes

Follow existing project patterns. Typical defaults:

- `200`: successful read or update with body;
- `201`: successful creation;
- `204`: successful operation with no body;
- `400`: malformed or invalid request;
- `401`: unauthenticated;
- `403`: authenticated but unauthorized;
- `404`: resource not found or intentionally hidden;
- `409`: conflict, such as uniqueness or version conflict;
- `422`: validation error when using FastAPI/Pydantic default behavior;
- `500`: unexpected server failure.

Do not return `200` for failed writes or unexpected errors.

## Pagination, Filtering, Sorting

- Paginate list endpoints that can grow.
- Validate filter and sort fields against an allowlist.
- Define stable ordering for paginated results.
- Include enough metadata for the frontend to render next/previous state according to existing project style.
- Avoid returning unbounded lists from endpoints likely to grow.

## Authentication And Authorization

- Backend authorization is the security boundary.
- Frontend checks may improve UX but must not be the only protection.
- Do not accept identity, role, owner ID, organization ID, or tenant scope from the client without backend verification.
- Define whether unauthenticated, unauthorized, and not-found cases are intentionally distinguishable.

## Frontend API Client Rules

- Centralize endpoint paths, methods, request typing, response parsing, and error normalization.
- Components should call API clients, actions, or hooks, not repeat raw `fetch` logic.
- Treat response payloads as untrusted unless generated/shared types and runtime behavior make the trust boundary explicit.
- Abort, ignore, or guard stale async work when inputs change or components unmount.

## Backend Route Rules

- Keep route handlers thin.
- Validate input, call the owning service/use case, return response models, and map expected errors.
- Do not put SQLAlchemy query construction or complex business policy in route handlers unless that is the established project boundary.

## Tests

- Backend contract tests should cover status codes, response shape, validation errors, and authorization behavior.
- Frontend tests should cover API client parsing/error mapping and user-visible behavior affected by contract changes.
- Breaking changes should include tests that fail under the old contract or document why that is not possible.

## Review Checklist

- Did every affected backend and frontend boundary change together?
- Are request and response models explicit?
- Are error codes and status codes stable and intentional?
- Is backend authorization enforced independently of frontend UI checks?
- Are list endpoints bounded and ordered?
- Is raw `fetch` avoided in components when an API client should own the contract?
- Are tests updated at the contract boundary?
