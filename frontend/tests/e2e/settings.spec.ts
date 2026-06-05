import { expect, test } from "@playwright/test"
import { installNotificationMocks } from "./helpers"

test.beforeEach(async ({ page }) => {
  await installNotificationMocks(page)
  await page.addInitScript(() => {
    window.localStorage.setItem("auth-token", "access.payload.sig")
    window.localStorage.setItem("refresh-token", "refresh.payload.sig")
    window.localStorage.setItem("user-info", JSON.stringify({ username: "admin" }))
    window.localStorage.setItem("config-wizard-completed", "true")
    window.localStorage.setItem("sidebar-collapsed", "false")
  })
  await page.route("**/api/health", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ success: true }) })
  })
  await page.route("**/api/**", async (route) => {
    const url = new URL(route.request().url())
    const path = url.pathname
    const payload = mockApiPayload(path)
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ success: true, data: payload, message: "ok" }) })
  })
})

test("opens settings routes and a representative config dialog", async ({ page }) => {
  await page.goto("/settings")
  await expect(page.getByRole("heading", { name: "设置" })).toBeVisible()

  await page.goto("/settings/config")
  await expect(page.getByRole("heading", { name: "配置管理" })).toBeVisible()
  await page.getByRole("button", { name: "新增厂家" }).click()
  await expect(page.getByRole("dialog", { name: "新增厂家" })).toBeVisible()
  await expect(page.getByLabel("厂家名称")).toBeVisible()

  await page.goto("/settings/database")
  await expect(page.getByRole("heading", { name: "数据库管理" })).toBeVisible()

  for (const [route, heading] of [
    ["/settings/logs", "操作日志"],
    ["/settings/system-logs", "系统日志"],
    ["/settings/sync", "多数据源同步"],
    ["/settings/cache", "缓存管理"],
    ["/settings/usage", "使用统计"],
    ["/settings/scheduler", "定时任务"]
  ] as const) {
    await page.goto(route)
    await expect(page.getByRole("heading", { name: heading, exact: true })).toBeVisible()
  }
})

test("keeps personal settings submenu visible after returning from config management", async ({ page }) => {
  await page.goto("/settings")
  await expect(page.getByRole("heading", { name: "设置" })).toBeVisible()

  const nav = page.getByRole("navigation")
  await expect(nav.getByRole("link", { name: "通用设置" })).toBeVisible()

  await page.getByRole("main").getByRole("link", { name: /配置管理/ }).click()
  await expect(page).toHaveURL(/\/settings\/config$/)
  await expect(page.getByRole("heading", { name: "配置管理" })).toBeVisible()

  await nav.getByRole("link", { name: "个人设置" }).click()
  await expect(page).toHaveURL(/\/settings$/)
  await expect(nav.getByRole("link", { name: "通用设置" })).toBeVisible()
  await expect(nav.getByRole("link", { name: "安全设置" })).toBeVisible()
})

test("navigates from the sidebar without reloading the app shell", async ({ page }) => {
  await page.goto("/dashboard")
  await expect(page.getByRole("heading", { name: "仪表板" })).toBeVisible()

  const initialNavigationCount = await page.evaluate(() => performance.getEntriesByType("navigation").length)
  const nav = page.getByRole("navigation")

  await nav.getByRole("link", { name: "我的自选股" }).click()
  await expect(page).toHaveURL(/\/favorites$/)
  await expect(page.getByRole("heading", { name: "我的自选股" })).toBeVisible()

  await nav.getByRole("link", { name: "设置" }).click()
  await expect(page).toHaveURL(/\/settings$/)
  await nav.getByRole("link", { name: "系统管理" }).click()
  await nav.getByRole("link", { name: "定时任务" }).click()
  await expect(page).toHaveURL(/\/settings\/scheduler$/)
  await expect(page.getByRole("heading", { name: "定时任务", exact: true })).toBeVisible()

  await expect
    .poll(() => page.evaluate(() => performance.getEntriesByType("navigation").length))
    .toBe(initialNavigationCount)
})

function mockApiPayload(path: string) {
  switch (path) {
    case "/api/health":
      return { ok: true }
    case "/api/config/llm/providers":
      return [{ id: "dashscope", name: "dashscope", display_name: "通义千问", is_active: true, supported_features: [], extra_config: { has_api_key: true } }]
    case "/api/config/llm":
      return [{ provider: "dashscope", model_name: "qwen-turbo", max_tokens: 2000, temperature: 0.7, timeout: 60, retry_times: 2, enabled: true }]
    case "/api/config/datasource":
      return [{ name: "tushare", type: "stock", timeout: 30, rate_limit: 100, enabled: true, priority: 1, config_params: {}, display_name: "Tushare" }]
    case "/api/config/market-categories":
      return [{ id: "cn", name: "cn", display_name: "A股", enabled: true, sort_order: 1 }]
    case "/api/config/datasource-groupings":
      return [{ data_source_name: "tushare", market_category_id: "cn", priority: 1, enabled: true }]
    case "/api/config/database":
      return [{ name: "default", type: "postgresql", host: "localhost", port: 5432, database: "trading_agents_cn", connection_params: {}, pool_size: 5, max_overflow: 10, enabled: true }]
    case "/api/config/settings":
      return { enable_cache: true, cache_ttl: 3600 }
    case "/api/config/model-catalog":
      return [{ provider: "dashscope", provider_name: "通义千问", models: [{ name: "qwen-turbo", display_name: "通义千问 Turbo" }] }]
    case "/api/system/database/status":
      return {
        postgres: { connected: true, host: "localhost", port: 5432, database: "trading_agents_cn", version: "15" },
        redis: { connected: true, host: "localhost", port: 6379, database: 0, version: "7" }
      }
    case "/api/system/database/stats":
      return { total_collections: 3, total_documents: 12, total_size: 2048, collections: [] }
    case "/api/system/logs/list":
      return { logs: [], total: 0, page: 1, page_size: 50, total_pages: 0 }
    case "/api/system/logs/stats":
      return { total_logs: 0, success_logs: 0, failed_logs: 0, success_rate: 0, action_type_distribution: {}, hourly_distribution: [] }
    case "/api/system/system-logs/files":
      return []
    case "/api/system/system-logs/statistics":
      return { total_files: 0, total_size_mb: 0, error_files: 0, recent_errors: [], log_types: {} }
    case "/api/sync/multi-source/status":
      return { job: "stock_basics", status: "idle", total: 0, inserted: 0, updated: 0, errors: 0, data_sources_used: [] }
    case "/api/sync/multi-source/sources/status":
      return [{ name: "tushare", priority: 1, available: true, description: "Tushare" }]
    case "/api/sync/multi-source/recommendations":
      return { primary_source: { name: "tushare", priority: 1, reason: "默认" }, fallback_sources: [], suggestions: [], warnings: [] }
    case "/api/sync/multi-source/history":
      return { records: [], total: 0, page: 1, page_size: 20, has_more: false }
    case "/api/cache/stats":
      return { totalFiles: 0, totalSize: 0, maxSize: 1024, stockDataCount: 0, newsDataCount: 0, analysisDataCount: 0 }
    case "/api/cache/details":
      return { items: [], total: 0, page: 1, page_size: 20 }
    case "/api/cache/backend-info":
      return { system: "hybrid", primary_backend: "redis", fallback_enabled: true }
    case "/api/usage/statistics":
      return { total_requests: 0, total_input_tokens: 0, total_output_tokens: 0, total_cost: 0, cost_by_currency: {}, by_provider: {}, by_model: {}, by_date: {} }
    case "/api/usage/records":
      return { records: [], total: 0 }
    case "/api/scheduler/jobs":
      return []
    case "/api/scheduler/stats":
      return { total_jobs: 0, running_jobs: 0, paused_jobs: 0, scheduler_running: true, scheduler_state: 1 }
    case "/api/scheduler/health":
      return { status: "healthy", running: true, state: 1, timestamp: new Date().toISOString() }
    default:
      return {}
  }
}
