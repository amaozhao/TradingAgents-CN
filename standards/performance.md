# Performance Standard

This standard covers query performance, payload size, caching, external calls, async behavior, frontend rendering, bundle size, and measurement.

## Core Rule

Do not optimize blindly, but do not introduce obvious performance regressions. Performance changes must preserve correctness, security, and clarity.

Prefer measuring or reasoning from a concrete bottleneck before adding cache layers, concurrency, memoization, or complex query rewrites.

## Backend Queries

Watch for:

- N+1 queries;
- unbounded result sets;
- missing tenant/user scope filters;
- missing deterministic ordering for pagination;
- loading full objects when only a few fields are needed;
- accidental lazy loading in async paths;
- expensive counts on large tables;
- missing indexes for new high-volume query patterns.

Rules:

- always paginate data that can grow;
- use deterministic sort order;
- select only required fields in performance-sensitive paths;
- eager load relationships intentionally;
- add indexes through migrations when justified;
- test query behavior when a change fixes or risks N+1 behavior.

## Transactions

Long transactions reduce concurrency and increase failure risk.

Rules:

- keep transactions scoped to one business operation;
- avoid slow external calls inside open database transactions;
- avoid waiting on user input or unrelated I/O during a transaction;
- use `flush()` rather than early commits when IDs are needed inside the same transaction;
- avoid splitting atomic workflows across multiple commits unless partial success is intended.

## External Calls

External calls should have:

- timeouts;
- bounded retries only when safe;
- clear adapter boundaries;
- latency/failure logging or metrics when important;
- batching or concurrency controls for loops.

Do not make slow external calls in a loop without considering batching, rate limits, and partial failures.

## Async Behavior

Async code should remain non-blocking.

Avoid:

- blocking file/network/database operations in async request paths;
- CPU-heavy work inside the event loop;
- unbounded `gather` or parallel calls;
- fire-and-forget tasks without lifecycle and error handling;
- `asyncio.run()` inside running event loops.

Use bounded concurrency when processing many items.

## Caching

Caching must be explicit.

Define:

- cache key;
- value type;
- TTL or invalidation policy;
- owner;
- tenant/user scope;
- stale data tolerance;
- failure behavior.

Do not add cache layers to hide inefficient or incorrect queries without understanding correctness. Do not cache sensitive data without reviewing scope and invalidation.

## Payload Size

Avoid returning unnecessary data across backend/frontend boundaries.

Rules:

- keep response models fit for the UI/use case;
- avoid embedding large nested relationships by default;
- paginate large collections;
- avoid logging large payloads;
- compress or stream only when the project pattern supports it and the use case warrants it.

## Frontend Bundle Size

Watch for:

- unnecessary `use client` boundaries;
- heavy dependencies in client components;
- importing entire libraries for a small utility;
- moving server-only logic into client bundles;
- large route-level components that cannot split naturally.

Use dynamic import only when it improves user experience and does not obscure code unnecessarily.

## React Rendering

Avoid premature memoization, but prevent obvious re-render problems.

Check:

- expensive calculations in render;
- unstable object/function props passed deeply;
- large lists without pagination/virtualization when needed;
- global state updates that rerender unrelated UI;
- effects that refetch or recompute unnecessarily.

Use `useMemo`/`useCallback` only when they address a concrete stability or cost issue.

## Images And Assets

Rules:

- use existing Next.js/image patterns where configured;
- provide correct dimensions when required;
- avoid shipping large unoptimized images;
- lazy-load non-critical media when appropriate;
- avoid adding large assets for minor UI polish.

## Measurement

Prefer evidence when changing performance behavior:

- failing test or benchmark;
- query count/log output;
- profiler observation;
- bundle analyzer output if available;
- production-like symptom from the task.

When measurement is not available, state the reasoning and keep changes conservative.

## Review Checklist

- Did the change introduce unbounded queries or payloads?
- Are pagination and ordering correct?
- Are transactions kept short?
- Are external calls bounded and observable?
- Is caching scoped and invalidated correctly?
- Did the change avoid unnecessary client bundle growth?
- Are rendering optimizations justified rather than decorative?
