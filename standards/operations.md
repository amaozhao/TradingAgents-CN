# Operations Standard

This standard covers dependencies, lockfiles, environment variables, runtime configuration, feature flags, logging, metrics, tracing, and operational diagnostics.

## Core Rule

Operational code should be explicit, typed, observable, and minimal. Do not introduce dependencies, configuration, logging, or runtime behavior that obscures correctness or expands maintenance burden without clear value.

## Dependencies

Do not add dependencies casually. Prefer existing project dependencies and standard library/platform capabilities.

A new dependency may be appropriate when:

- the functionality is non-trivial and risky to implement locally;
- the package is a maintained standard choice;
- it is compatible with the current stack;
- it reduces security or correctness risk;
- it integrates with existing project tooling;
- the user explicitly requested it.

A new dependency is usually not appropriate when:

- it replaces a few lines of simple code;
- it is used once for a small feature;
- it duplicates an existing dependency;
- it has unclear maintenance;
- it significantly increases frontend bundle size;
- it introduces security-sensitive behavior without review.

Rules:

- update the relevant lockfile when package metadata changes;
- distinguish runtime and development dependencies;
- do not downgrade Next.js, React, TypeScript, or related framework packages unless explicitly requested;
- do not edit dependency output such as `node_modules/`;
- wrap third-party SDKs behind project-owned adapters when used by application logic.

## Configuration

Configuration is untrusted input. Validate it at the boundary and expose typed configuration to application code.

Rules:

- centralize configuration loading where project patterns allow;
- validate required variables at startup;
- parse booleans, numbers, URLs, durations, and lists explicitly;
- use safe defaults only when absence is genuinely acceptable;
- fail fast for missing required configuration;
- avoid ad hoc environment reads scattered across modules;
- keep `.env.example` fake and useful;
- do not put server secrets in client-visible variables.

Backend code should depend on typed settings objects. Frontend code should distinguish public config from server-only config.

## Feature Flags

Feature flags should have clear ownership and lifecycle.

Define:

- flag name;
- purpose;
- default behavior;
- server/client visibility;
- rollout target;
- removal condition;
- testing strategy.

Do not leave stale flags indefinitely. Do not use frontend-only flags for security decisions.

## Logging

Logs should support debugging and operations without leaking sensitive data.

Rules:

- use structured logging if that is the project pattern;
- include request ID, actor ID, organization ID, operation, or resource ID when safe and useful;
- redact secrets and sensitive personal data;
- avoid logging large raw bodies;
- avoid duplicate logging of the same exception at many layers;
- use appropriate log levels.

Suggested levels:

- debug: detailed development diagnostics;
- info: successful high-level operations worth tracking;
- warning: recoverable unusual behavior;
- error: failed operation needing attention;
- critical: system-level failure.

## Metrics

Add metrics only when they answer an operational question.

Useful metrics include:

- request count/latency/error rate;
- external dependency latency/failure rate;
- queue depth and job failures;
- cache hit rate;
- feature-specific business counters.

Metrics should avoid high-cardinality labels such as raw user IDs, emails, URLs, or free-form error messages unless the observability system explicitly supports them safely.

## Tracing

Tracing is useful for cross-boundary latency and failure diagnosis.

When adding spans or trace context:

- use existing instrumentation patterns;
- avoid leaking secrets in span attributes;
- add spans around meaningful external calls or expensive operations;
- keep span names stable and low-cardinality.

## Diagnostics And Health

Operational endpoints or diagnostics should expose only safe information.

Do not expose secrets, internal stack traces, full environment dumps, or user data.

Health checks should distinguish readiness and liveness when the project supports that distinction.

## Background Work

Background tasks should have owned lifecycle, error handling, retry policy, and observability.

Do not create fire-and-forget tasks from request paths unless the project has a supervised task mechanism and the task is safe if the request completes or fails.

## Review Checklist

- Is a new dependency justified and locked?
- Is configuration typed and validated?
- Are secrets kept server-only and redacted?
- Are logs useful without leaking sensitive data?
- Are metrics/traces low-cardinality and actionable?
- Are feature flags owned and removable?
- Are background tasks supervised and observable?
