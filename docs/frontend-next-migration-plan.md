# Frontend Next Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a functionally equivalent Next.js App Router + React frontend in `frontend-next/`, then cut over only after full verification.

**Architecture:** The migration runs in parallel with the existing Vue frontend. Next pages stay thin and delegate business behavior to `features/`; shared API, auth, route, and utility code lives under `libs/`; shared UI primitives and business components live under `components/`.

**Tech Stack:** Next.js App Router, React, TypeScript, pnpm, shadcn/ui, Radix, Tailwind, Zustand, TanStack Query, TanStack Table, React Hook Form, Zod, sonner, lucide-react, next-themes, ECharts, Vitest, React Testing Library, Playwright.

---

## Verification Gates

Run these before claiming the migration is ready to cut over:

```bash
cd frontend-next
pnpm lint
pnpm type-check
pnpm test
pnpm build
pnpm exec playwright test
```

Run deployment checks before cutover:

```bash
docker build -f deploy/docker/frontend.Dockerfile .
docker compose -f deploy/docker/compose/docker-compose.yml config
```

Run legacy baseline check before cutover:

```bash
cd frontend
yarn build
```

Manual browser regression must cover:

- `/login`
- login success redirect
- 401 clears auth and redirects to `/login`
- `/dashboard`
- `/analysis/single`
- `/analysis/batch`
- `/tasks`
- `/reports`
- `/reports/view/:id`
- `/stocks/:code`
- `/settings`
- `/settings/config`
- `/settings/database`
- `/settings/logs`
- `/settings/system-logs`
- `/settings/sync`
- `/settings/cache`
- `/settings/usage`
- `/settings/scheduler`
- `/learning`
- `/learning/:category`
- `/learning/article/:id`
- `/paper/:name.md` redirect
- WebSocket notification connect and reconnect
- light and dark theme
- browser console has no blocking runtime errors

## File Structure

Create the Next app under `frontend-next/`:

```text
frontend-next/
  app/
    layout.tsx
    providers.tsx
    login/page.tsx
    dashboard/page.tsx
    analysis/single/page.tsx
    analysis/batch/page.tsx
    screening/page.tsx
    favorites/page.tsx
    learning/page.tsx
    learning/[category]/page.tsx
    learning/article/[id]/page.tsx
    stocks/[code]/page.tsx
    tasks/page.tsx
    queue/page.tsx
    reports/page.tsx
    reports/view/[id]/page.tsx
    reports/token/page.tsx
    settings/page.tsx
    settings/config/page.tsx
    settings/database/page.tsx
    settings/logs/page.tsx
    settings/system-logs/page.tsx
    settings/sync/page.tsx
    settings/cache/page.tsx
    settings/usage/page.tsx
    settings/scheduler/page.tsx
    about/page.tsx
    paper/page.tsx
    paper/[name].md/page.tsx
    not-found.tsx
  components/
    ui/
    layout/
    data-table/
    feedback/
    charts/
  features/
    analysis/
    reports/
    settings/
    stocks/
    learning/
    notifications/
    tasks/
    favorites/
    screening/
    dashboard/
    auth/
  libs/
    api/
    routes/
    auth/
    utils/
  stores/
  hooks/
  types/
  styles/
  tests/
```

## Task 1: Scaffold `frontend-next`

**Files:**

- Create: `frontend-next/package.json`
- Create: `frontend-next/pnpm-lock.yaml`
- Create: `frontend-next/next.config.ts`
- Create: `frontend-next/tsconfig.json`
- Create: `frontend-next/eslint.config.mjs`
- Create: `frontend-next/postcss.config.mjs`
- Create: `frontend-next/tailwind.config.ts`
- Create: `frontend-next/components.json`
- Create: `frontend-next/app/layout.tsx`
- Create: `frontend-next/app/providers.tsx`
- Create: `frontend-next/app/globals.css`
- Create: `frontend-next/libs/utils/cn.ts`

- [x] Create the Next app in `frontend-next/` with TypeScript, App Router, Tailwind, ESLint, and pnpm.
- [x] Initialize shadcn with `new-york`, `slate`, CSS variables, lucide icons, RSC enabled, and aliases using `@/libs/utils`.
- [x] Add baseline shadcn components: button, input, label, form, dialog, alert-dialog, dropdown-menu, select, tabs, table, tooltip, badge, card, separator, sheet, skeleton, command, popover, toast/sonner.
- [x] Set `next.config.ts` to `output: 'standalone'`.
- [x] Add development rewrites for `/api/:path*` to `http://localhost:8000/api/:path*`.
- [x] Add scripts: `dev`, `build`, `start`, `lint`, `type-check`, `test`, `test:e2e`.
- [x] Verify `pnpm lint`, `pnpm type-check`, and `pnpm build`.
- [x] Commit scaffold with a Lore commit.

## Task 2: Build Foundation Providers

**Files:**

- Modify: `frontend-next/app/providers.tsx`
- Create: `frontend-next/stores/auth-store.ts`
- Create: `frontend-next/stores/app-store.ts`
- Create: `frontend-next/stores/notification-store.ts`
- Create: `frontend-next/libs/auth/token-storage.ts`
- Create: `frontend-next/libs/api/client.ts`
- Create: `frontend-next/libs/api/types.ts`
- Create: `frontend-next/libs/api/query-client.ts`
- Create: `frontend-next/components/feedback/global-toaster.tsx`
- Create: `frontend-next/components/feedback/error-state.tsx`
- Create: `frontend-next/components/feedback/empty-state.tsx`
- Create: `frontend-next/components/feedback/confirm-dialog.tsx`

- [x] Implement token storage using `auth-token`, `refresh-token`, and `user-info`.
- [x] Implement Zustand auth store with login state, redirect path, user info, and clear-auth behavior.
- [x] Implement app store for theme, sidebar, language, network status, and API connection state.
- [x] Implement notification store with drawer state, unread count, WebSocket status, and reconnect state.
- [x] Implement axios client preserving `ApiResponse<T>`, timeout, `Authorization` header, `Accept-Language`, request ID, business error handling, and 401 cleanup.
- [x] Integrate TanStack Query provider and clear QueryClient cache on logout.
- [x] Integrate next-themes and sonner in `app/providers.tsx`.
- [x] Add unit tests for token storage, auth store, and API 401 handling.
- [x] Verify `pnpm test`, `pnpm lint`, `pnpm type-check`, and `pnpm build`.
- [x] Commit foundation with a Lore commit.

## Task 3: Build Route Shell

**Files:**

- Create: `frontend-next/libs/routes/route-config.ts`
- Create: `frontend-next/libs/routes/redirects.ts`
- Create: `frontend-next/components/layout/app-shell.tsx`
- Create: `frontend-next/components/layout/sidebar.tsx`
- Create: `frontend-next/components/layout/sidebar-menu.tsx`
- Create: `frontend-next/components/layout/header.tsx`
- Create: `frontend-next/components/layout/breadcrumb.tsx`
- Create: `frontend-next/components/layout/user-menu.tsx`
- Create: `frontend-next/components/layout/footer.tsx`
- Create: `frontend-next/components/layout/protected-route.tsx`
- Create: `frontend-next/app/(protected)/layout.tsx` if route groups are used

- [x] Encode all current Vue routes, menu metadata, titles, icons, hidden flags, and auth requirements in `route-config.ts`.
- [x] Map old Element Plus icon names to lucide-react icons.
- [x] Implement AppShell with sidebar, header, breadcrumb, user menu, footer, responsive collapse, and content wrapper.
- [x] Implement client route guard for protected pages and `/login` redirect behavior.
- [x] Implement `/queue`, `/analysis/history`, and `/paper/:name.md` redirects.
- [x] Add Playwright test for unauthenticated protected route redirect.
- [x] Add Playwright test for logged-in `/login` redirect to `/dashboard`.
- [x] Verify `pnpm test`, `pnpm exec playwright test`, `pnpm lint`, `pnpm type-check`, and `pnpm build`.
- [x] Commit route shell with a Lore commit.

## Task 4: Build Shared Business Components

**Files:**

- Create: `frontend-next/components/data-table/data-table.tsx`
- Create: `frontend-next/components/data-table/data-table-pagination.tsx`
- Create: `frontend-next/components/data-table/data-table-toolbar.tsx`
- Create: `frontend-next/components/data-table/data-table-column-header.tsx`
- Create: `frontend-next/components/charts/e-chart-panel.tsx`
- Create: `frontend-next/components/feedback/async-button.tsx`
- Create: `frontend-next/components/feedback/page-header.tsx`
- Create: `frontend-next/features/learning/markdown-renderer.tsx`
- Create: `frontend-next/features/learning/mermaid-renderer.tsx`

- [x] Implement `DataTable` with TanStack Table, loading, empty, pagination, sorting, filtering, row actions, selection, and column visibility.
- [x] Implement `EChartPanel` with loading, empty, resize, theme, and dark-mode handling.
- [x] Implement shared PageHeader, AsyncButton, EmptyState, ErrorState, and ConfirmDialog patterns.
- [x] Implement Markdown and Mermaid renderers with dark-mode compatible styling.
- [x] Add component tests for DataTable empty/loading/rendered rows.
- [x] Add component tests for Zod form error display using shadcn Form.
- [x] Verify `pnpm test`, `pnpm lint`, `pnpm type-check`, and `pnpm build`.
- [x] Commit shared components with a Lore commit.

## Task 5: Migrate API Modules

**Files:**

- Create: `frontend-next/libs/api/analysis.ts`
- Create: `frontend-next/libs/api/auth.ts`
- Create: `frontend-next/libs/api/cache.ts`
- Create: `frontend-next/libs/api/config.ts`
- Create: `frontend-next/libs/api/database.ts`
- Create: `frontend-next/libs/api/favorites.ts`
- Create: `frontend-next/libs/api/logs.ts`
- Create: `frontend-next/libs/api/model-capabilities.ts`
- Create: `frontend-next/libs/api/multi-market.ts`
- Create: `frontend-next/libs/api/news.ts`
- Create: `frontend-next/libs/api/notifications.ts`
- Create: `frontend-next/libs/api/operation-logs.ts`
- Create: `frontend-next/libs/api/paper.ts`
- Create: `frontend-next/libs/api/scheduler.ts`
- Create: `frontend-next/libs/api/screening.ts`
- Create: `frontend-next/libs/api/stock-sync.ts`
- Create: `frontend-next/libs/api/stocks.ts`
- Create: `frontend-next/libs/api/sync.ts`
- Create: `frontend-next/libs/api/tags.ts`
- Create: `frontend-next/libs/api/templates.ts`
- Create: `frontend-next/libs/api/usage.ts`

- [ ] Port every current `frontend/src/api/*` module into `frontend-next/libs/api/*`.
- [ ] Preserve endpoint paths, method names, request payload shapes, and response shapes.
- [ ] Remove Vue Router, Pinia, Element Plus, and `import.meta.env` dependencies from API modules.
- [ ] Replace `VITE_API_BASE_URL` with same-origin `/api` default and optional `NEXT_PUBLIC_API_BASE_URL` override only where needed.
- [ ] Preserve the legacy `/api/stocks/quote` compatibility guard if current call sites still need it.
- [ ] Add unit tests for API client success response, business error response, auth error response, and endpoint URL rewrite guard.
- [ ] Verify `pnpm test`, `pnpm lint`, `pnpm type-check`, and `pnpm build`.
- [ ] Commit API migration with a Lore commit.

## Task 6: Migrate Auth, Dashboard, and App Initialization

**Files:**

- Create: `frontend-next/app/login/page.tsx`
- Create: `frontend-next/app/dashboard/page.tsx`
- Create: `frontend-next/features/auth/login-form.tsx`
- Create: `frontend-next/features/auth/register-form.tsx`
- Create: `frontend-next/features/dashboard/dashboard-page.tsx`
- Create: `frontend-next/features/config/config-wizard.tsx`
- Create: `frontend-next/components/layout/network-status.tsx`

- [ ] Migrate login and register behavior with React Hook Form + Zod.
- [ ] Preserve login success redirect to stored target path.
- [ ] Preserve invalid token cleanup on app initialization.
- [ ] Preserve API connectivity check and offline-tolerant startup behavior.
- [ ] Migrate dashboard with equivalent cards, statistics, charts, and navigation links.
- [ ] Migrate first-time configuration wizard behavior.
- [ ] Add Playwright tests for login, redirect, and protected dashboard access.
- [ ] Verify `pnpm test`, `pnpm exec playwright test`, `pnpm lint`, `pnpm type-check`, and `pnpm build`.
- [ ] Commit auth and dashboard migration with a Lore commit.

## Task 7: Migrate Analysis and Task Workflows

**Files:**

- Create: `frontend-next/app/analysis/single/page.tsx`
- Create: `frontend-next/app/analysis/batch/page.tsx`
- Create: `frontend-next/app/tasks/page.tsx`
- Create: `frontend-next/features/analysis/single-analysis-page.tsx`
- Create: `frontend-next/features/analysis/batch-analysis-page.tsx`
- Create: `frontend-next/features/tasks/task-center-page.tsx`

- [ ] Migrate single analysis page with equivalent inputs, model/deep model selectors, analyst selection, submit behavior, task creation, progress, and result navigation.
- [ ] Migrate batch analysis page with equivalent upload/input behavior and batch task handling.
- [ ] Migrate task center with active/completed tabs, polling/refetch behavior, actions, and result/report dialogs.
- [ ] Preserve `/analysis/history -> /tasks?tab=completed`.
- [ ] Add Playwright tests for navigation to analysis pages and task center tab behavior.
- [ ] Verify `pnpm test`, `pnpm exec playwright test`, `pnpm lint`, `pnpm type-check`, and `pnpm build`.
- [ ] Commit analysis and tasks migration with a Lore commit.

## Task 8: Migrate Reports

**Files:**

- Create: `frontend-next/app/reports/page.tsx`
- Create: `frontend-next/app/reports/view/[id]/page.tsx`
- Create: `frontend-next/app/reports/token/page.tsx`
- Create: `frontend-next/features/reports/reports-page.tsx`
- Create: `frontend-next/features/reports/report-detail-page.tsx`
- Create: `frontend-next/features/reports/token-statistics-page.tsx`
- Create: `frontend-next/features/reports/task-report-dialog.tsx`
- Create: `frontend-next/features/reports/task-result-dialog.tsx`

- [ ] Migrate report list with filters, pagination, actions, and navigation.
- [ ] Migrate report detail rendering with Markdown/Mermaid where applicable.
- [ ] Migrate token statistics charts/tables.
- [ ] Preserve `/reports/view/:id` dynamic route.
- [ ] Add Playwright tests for reports list and report detail route.
- [ ] Verify `pnpm test`, `pnpm exec playwright test`, `pnpm lint`, `pnpm type-check`, and `pnpm build`.
- [ ] Commit reports migration with a Lore commit.

## Task 9: Migrate Settings and System Pages

**Files:**

- Create: `frontend-next/app/settings/page.tsx`
- Create: `frontend-next/app/settings/config/page.tsx`
- Create: `frontend-next/app/settings/database/page.tsx`
- Create: `frontend-next/app/settings/logs/page.tsx`
- Create: `frontend-next/app/settings/system-logs/page.tsx`
- Create: `frontend-next/app/settings/sync/page.tsx`
- Create: `frontend-next/app/settings/cache/page.tsx`
- Create: `frontend-next/app/settings/usage/page.tsx`
- Create: `frontend-next/app/settings/scheduler/page.tsx`
- Create: `frontend-next/features/settings/`
- Create: `frontend-next/features/system/`

- [ ] Migrate settings index and config management.
- [ ] Migrate LLM provider, model catalog, data source, grouping, market category, and sortable source dialogs with React Hook Form + Zod.
- [ ] Migrate database management, operation logs, system logs, sync, cache, usage, and scheduler pages.
- [ ] Preserve destructive action confirmations through AlertDialog.
- [ ] Add Playwright tests for settings navigation and one representative config dialog.
- [ ] Verify `pnpm test`, `pnpm exec playwright test`, `pnpm lint`, `pnpm type-check`, and `pnpm build`.
- [ ] Commit settings and system migration with a Lore commit.

## Task 10: Migrate Stocks, Screening, Favorites, and Paper Trading

**Files:**

- Create: `frontend-next/app/stocks/[code]/page.tsx`
- Create: `frontend-next/app/screening/page.tsx`
- Create: `frontend-next/app/favorites/page.tsx`
- Create: `frontend-next/app/paper/page.tsx`
- Create: `frontend-next/features/stocks/stock-detail-page.tsx`
- Create: `frontend-next/features/screening/screening-page.tsx`
- Create: `frontend-next/features/favorites/favorites-page.tsx`
- Create: `frontend-next/features/paper/paper-trading-page.tsx`

- [ ] Migrate stock detail page and preserve `/stocks/:code`.
- [ ] Migrate multi-market stock search and market utilities.
- [ ] Migrate screening filters, results table, tags, and saved/favorite actions.
- [ ] Migrate favorites list, actions, and navigation.
- [ ] Migrate paper trading page with equivalent forms, analysis integration, and tables.
- [ ] Add Playwright tests for stock dynamic route and screening page load.
- [ ] Verify `pnpm test`, `pnpm exec playwright test`, `pnpm lint`, `pnpm type-check`, and `pnpm build`.
- [ ] Commit market-related pages with a Lore commit.

## Task 11: Migrate Learning and About

**Files:**

- Create: `frontend-next/app/learning/page.tsx`
- Create: `frontend-next/app/learning/[category]/page.tsx`
- Create: `frontend-next/app/learning/article/[id]/page.tsx`
- Create: `frontend-next/app/paper/[name].md/page.tsx`
- Create: `frontend-next/app/about/page.tsx`
- Create: `frontend-next/features/learning/learning-home-page.tsx`
- Create: `frontend-next/features/learning/learning-category-page.tsx`
- Create: `frontend-next/features/learning/learning-article-page.tsx`
- Create: `frontend-next/features/about/about-page.tsx`

- [ ] Migrate learning home, category, and article pages.
- [ ] Preserve docs-backed content loading.
- [ ] Preserve Markdown and Mermaid rendering.
- [ ] Preserve `/paper/:name.md -> /learning/article/:name` redirect.
- [ ] Migrate about page content and assets.
- [ ] Add Playwright tests for learning article and paper redirect.
- [ ] Verify `pnpm test`, `pnpm exec playwright test`, `pnpm lint`, `pnpm type-check`, and `pnpm build`.
- [ ] Commit learning and about migration with a Lore commit.

## Task 12: Migrate Notifications and WebSocket

**Files:**

- Create: `frontend-next/features/notifications/notification-drawer.tsx`
- Create: `frontend-next/features/notifications/notification-bell.tsx`
- Modify: `frontend-next/stores/notification-store.ts`
- Modify: `frontend-next/components/layout/header.tsx`

- [ ] Connect WebSocket to `ws(s)://<current-host>/api/ws/notifications?token=<token>`.
- [ ] Preserve reconnect backoff and max attempts.
- [ ] Preserve unread count refresh, mark read, mark all read, and notification insertion behavior.
- [ ] Disconnect WebSocket on logout.
- [ ] Add unit tests for notification reducer/store behavior.
- [ ] Add manual verification step for WebSocket connect and reconnect.
- [ ] Verify `pnpm test`, `pnpm lint`, `pnpm type-check`, and `pnpm build`.
- [ ] Commit notification migration with a Lore commit.

## Task 13: Complete Visual and Behavior Parity Pass

**Files:**

- Modify: `frontend-next/features/**`
- Modify: `frontend-next/components/**`
- Modify: `frontend-next/styles/**`

- [ ] Compare every current Vue route against its Next route.
- [ ] Confirm page title, menu visibility, breadcrumb, loading state, empty state, error state, primary action, and destructive confirmation for every route.
- [ ] Confirm light and dark theme readability for charts, Markdown, Mermaid, tables, forms, dialogs, and toasts.
- [ ] Confirm responsive layout for desktop and mobile widths.
- [ ] Confirm browser console has no blocking runtime errors during core flows.
- [ ] Verify `pnpm test`, `pnpm exec playwright test`, `pnpm lint`, `pnpm type-check`, and `pnpm build`.
- [ ] Commit parity pass with a Lore commit.

## Task 14: Add Docker and Compose Cutover

**Files:**

- Modify: `deploy/docker/frontend.Dockerfile`
- Modify: `deploy/docker/compose/docker-compose.yml`
- Modify: `deploy/docker/compose/docker-compose.hub.nginx.yml`
- Modify: `deploy/docker/compose/docker-compose.hub.nginx.arm.yml`
- Modify: `deploy/docker/nginx/frontend.conf` if still used by a reverse proxy path
- Modify: `docs/repo-structure.md`
- Modify: `README.md` if startup commands are documented there

- [ ] Update frontend Dockerfile to build `frontend-next` with pnpm and run Next standalone server.
- [ ] Ensure Docker build copies `.next/standalone`, `.next/static`, `public`, and required docs assets.
- [ ] Change frontend service port mapping from `3000:80` to `3000:3000` where appropriate.
- [ ] Keep production `/api` and WebSocket proxying at the outer Nginx layer.
- [ ] Update CORS origins only if runtime evidence shows the backend rejects the new frontend origin.
- [ ] Run `docker build -f deploy/docker/frontend.Dockerfile .`.
- [ ] Run `docker compose -f deploy/docker/compose/docker-compose.yml config`.
- [ ] Verify `cd frontend-next && pnpm build`.
- [ ] Commit deployment cutover with a Lore commit.

## Task 15: Final Cutover and Legacy Frontend Handling

**Files:**

- Move: `frontend-next/` to `frontend/`
- Move or delete: old `frontend/` according to final cutover decision
- Modify: `deploy/docker/frontend.Dockerfile`
- Modify: `deploy/docker/compose/*.yml`
- Modify: `docs/frontend-next-migration-design.md`
- Modify: `docs/frontend-next-migration-plan.md`
- Modify: `docs/repo-structure.md`
- Modify: `README.md`

- [ ] Before moving directories, verify old Vue baseline with `cd frontend && yarn build`.
- [ ] Move old Vue frontend to `frontend-vue/` or remove it only after Next passes full acceptance.
- [ ] Move `frontend-next/` to `frontend/`.
- [ ] Update paths in Dockerfiles, Compose files, docs, scripts, and README.
- [ ] Search for stale `frontend-next`, `VITE_API_BASE_URL`, `vue`, `pinia`, `element-plus`, and old frontend path references.
- [ ] Run `cd frontend && pnpm lint`.
- [ ] Run `cd frontend && pnpm type-check`.
- [ ] Run `cd frontend && pnpm test`.
- [ ] Run `cd frontend && pnpm build`.
- [ ] Run `cd frontend && pnpm exec playwright test`.
- [ ] Run `docker build -f deploy/docker/frontend.Dockerfile .`.
- [ ] Run `docker compose -f deploy/docker/compose/docker-compose.yml config`.
- [ ] Complete manual browser regression checklist from the Verification Gates section.
- [ ] Commit final cutover with a Lore commit.

## Task 16: Post-Cutover Cleanup

**Files:**

- Modify: `docs/frontend-next-migration-design.md`
- Modify: `docs/frontend-next-migration-plan.md`
- Modify: `docs/repo-structure.md`
- Modify: `README.md`
- Modify: any CI, script, or deploy docs that still mention the old Vue workflow

- [ ] Remove obsolete Vue-only generated files if old Vue frontend is deleted.
- [ ] Remove stale Yarn frontend instructions from docs only after the old Vue tree is no longer the active frontend.
- [ ] Keep historical notes about the migration and rollback point in the design doc.
- [ ] Run repo-wide search for stale old frontend commands.
- [ ] Run final frontend and Docker verification.
- [ ] Commit cleanup with a Lore commit.

## Rollback Rules

- During migration, rollback is simply continuing to use existing `frontend/`.
- Do not modify default Docker frontend entrypoints until the deploy cutover task.
- Do not archive or delete old Vue frontend until the final cutover task.
- Keep deploy cutover and legacy cleanup in separate commits so cutover can be reverted independently.

## Open Implementation Notes

- Use exact current backend API behavior as source of truth. Do not infer new contracts from UI convenience.
- If a Vue page has unclear behavior, inspect the page and API module before rewriting it.
- If a current Vue bug is discovered, record it. Do not silently "fix" behavior in Next unless the fix is required for functional parity or approved as a migration correction.
- Preserve current URLs even if a cleaner Next route exists.
- Keep each stage buildable before moving to the next stage.
