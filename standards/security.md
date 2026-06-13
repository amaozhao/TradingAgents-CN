# Security Standard

This standard covers authentication, authorization, tenant isolation, secrets, untrusted input, uploads, redirects, webhooks, and sensitive logging.

## Core Rule

Backend enforcement is the security boundary. Frontend checks improve user experience but do not provide security.

Never hide security-sensitive failures with broad fallbacks or generic success responses.

## Authentication

Authentication identifies the actor.

Rules:

- use existing authentication middleware/dependencies;
- do not parse or validate tokens ad hoc in feature code unless that is the established boundary;
- do not log tokens, cookies, authorization headers, session IDs, or credentials;
- keep missing, expired, malformed, and invalid credentials behavior consistent with the API contract;
- use secure defaults for unauthenticated requests.

## Authorization

Authorization decides whether the actor can perform an action.

Rules:

- enforce authorization on the backend;
- apply authorization to reads and writes;
- check tenant/organization/user ownership in queries or service policy;
- do not rely on hidden frontend buttons;
- avoid fetching globally and filtering only on the frontend;
- return `404` instead of `403` when hiding resource existence is required by contract.

Centralize repeated authorization logic in policies or services. Do not duplicate complex permission logic across routes/components.

## Tenant Isolation

For multi-tenant or organization-scoped data:

- include tenant scope in database queries;
- include tenant scope in mutations;
- verify ownership before side effects;
- avoid accepting tenant IDs from clients without validating actor access;
- ensure background jobs and adapters preserve tenant context;
- test cross-tenant access denial.

## Secrets

Secrets include API keys, tokens, passwords, private keys, database URLs, signing secrets, webhook secrets, and OAuth client secrets.

Rules:

- do not hard-code secrets;
- do not commit real secrets;
- keep `.env.example` values fake;
- do not expose server secrets to frontend bundles;
- redact secrets in logs and errors;
- validate required secrets through typed configuration.

See `operations.md` for configuration loading rules.

## Input Validation

Treat client input, external SDK payloads, webhook bodies, uploaded files, environment variables, and database content from older versions as untrusted until validated at the relevant boundary.

Rules:

- validate request bodies with Pydantic or existing schema mechanisms;
- validate frontend API responses when no generated contract exists;
- validate file names, content types, sizes, and storage paths;
- validate redirect targets;
- validate webhook signatures before processing payloads;
- avoid trusting hidden form fields for authorization-critical values.

## Injection Risks

### SQL Injection

Use SQLAlchemy parameterization and expression APIs. Keep raw SQL rare, parameterized, justified, and tested.

Do not build SQL by string concatenation with user-controlled values.

### XSS

Do not render untrusted HTML. Avoid `dangerouslySetInnerHTML` unless the content is sanitized by a trusted project-owned boundary and the task explicitly requires HTML rendering.

Escape or validate user-generated content according to rendering context.

### Command And Path Injection

Do not pass unsanitized input to shell commands. Prefer library APIs over shell execution.

Normalize and constrain file paths. Prevent path traversal with user-controlled filenames or paths.

## SSRF

Server-side code must not fetch arbitrary user-provided URLs without validation and allowlisting appropriate to the feature.

Check:

- protocol;
- hostname/IP restrictions;
- redirects;
- private network access;
- timeouts;
- response size limits.

## Uploads

For file uploads, define:

- allowed content types/extensions;
- maximum file size;
- storage location;
- filename normalization;
- scan/validation requirements if applicable;
- access control;
- lifecycle/cleanup rules.

Do not trust original filenames or client-provided content types alone.

## Redirects

Avoid open redirects. Redirect only to relative paths or allowlisted origins.

Do not accept arbitrary `next` or `redirect` parameters without validation.

## Webhooks

Webhook handlers should:

- verify signatures before parsing trusted semantics;
- handle replay/idempotency when provider supports it;
- avoid logging sensitive payloads;
- process only known event types;
- return correct status codes for accepted/rejected events.

## Sensitive Logging

Do not log:

- authorization headers;
- cookies;
- tokens;
- passwords;
- private keys;
- full database URLs;
- raw payment or identity data;
- large raw request bodies.

Log safe identifiers and request IDs instead.

## Frontend Security

Frontend should not contain secrets or security-only enforcement. It may:

- hide actions the actor cannot use;
- show friendly auth/permission messages;
- avoid exposing unnecessary data in the UI;
- use safe link and form behavior.

But backend must still enforce permissions.

## Review Checklist

- Is backend authorization enforced for reads and writes?
- Is tenant scope included in queries and mutations?
- Are secrets protected from source, logs, and client bundles?
- Is untrusted input validated at the boundary?
- Are redirects, uploads, webhooks, and external URLs safe?
- Did the change avoid leaking sensitive data in errors or logs?
- Are security-critical paths tested?
