import { expect, test } from "@playwright/test"
import { installNotificationMocks } from "./helpers"

test.beforeEach(async ({ page }) => {
  await installNotificationMocks(page)
  await page.addInitScript(() => {
    window.localStorage.setItem("auth-token", "access.payload.sig")
    window.localStorage.setItem("refresh-token", "refresh.payload.sig")
    window.localStorage.setItem("user-info", JSON.stringify({ username: "admin" }))
    window.localStorage.setItem("config-wizard-completed", "true")
    window.localStorage.setItem("theme", "light")
  })
  await page.route("**/api/**", async (route) => {
    const url = new URL(route.request().url())
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ success: true, data: mockApiPayload(url.pathname), message: "ok" })
    })
  })
})

test("preserves page titles, core shell behavior, and notification drawer", async ({ page }) => {
  const blockingErrors: string[] = []
  page.on("pageerror", (error) => blockingErrors.push(error.message))
  page.on("console", (message) => {
    if (message.type() === "error") {
      blockingErrors.push(message.text())
    }
  })

  for (const [route, title, heading] of [
    ["/dashboard", "仪表板 - AGENTrader", "欢迎使用 AGENTrader"],
    ["/analysis/single", "个股分析 - AGENTrader", "个股分析"],
    ["/analysis/batch", "批量分析 - AGENTrader", "批量分析"],
    ["/tasks", "任务中心 - AGENTrader", "任务中心"],
    ["/reports", "分析报告 - AGENTrader", "分析报告"],
    ["/reports/view/r1", "报告详情 - AGENTrader", "贵州茅台 分析报告"],
    ["/reports/token", "Token统计 - AGENTrader", "Token使用统计"],
    ["/screening", "股票筛选 - AGENTrader", "股票筛选"],
    ["/favorites", "我的自选股 - AGENTrader", "我的自选股"],
    ["/paper", "模拟交易 - AGENTrader", "模拟交易"],
    ["/stocks/000001", "股票详情 - AGENTrader", "平安银行"],
    ["/settings", "设置 - AGENTrader", "设置"],
    ["/settings/config", "配置管理 - AGENTrader", "配置管理"],
    ["/settings/database", "数据库管理 - AGENTrader", "数据库管理"],
    ["/settings/logs", "操作日志 - AGENTrader", "操作日志"],
    ["/settings/system-logs", "系统日志 - AGENTrader", "系统日志"],
    ["/settings/sync", "多数据源同步 - AGENTrader", "多数据源同步"],
    ["/settings/cache", "缓存管理 - AGENTrader", "缓存管理"],
    ["/settings/usage", "使用统计 - AGENTrader", "使用统计"],
    ["/settings/scheduler", "定时任务 - AGENTrader", "定时任务"],
    ["/learning", "学习中心 - AGENTrader", "学习中心"],
    ["/learning/ai-basics", "学习分类 - AGENTrader", "AI基础知识"],
    ["/learning/article/what-is-llm", "文章详情 - AGENTrader", "什么是大语言模型（LLM）？"],
    ["/about", "关于 - AGENTrader", "AGENTrader"]
  ] as const) {
    await page.goto(route)
    await expect(page).toHaveTitle(title)
    await expect(page.getByRole("heading", { name: heading }).first()).toBeVisible()
  }

  await page.goto("/dashboard")
  await page.getByRole("button", { name: /^通知/ }).click()
  await expect(page.getByRole("dialog", { name: "消息中心" })).toBeVisible()
  await expect(page.getByText("暂无通知")).toBeVisible()

  await page.keyboard.press("Escape")
  await page.getByRole("button", { name: "切换主题" }).click()
  await expect(page.locator("html")).toHaveClass(/dark/)

  expect(blockingErrors).toEqual([])
})

test("keeps the app shell usable on mobile width", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto("/dashboard")

  await expect(page.getByRole("heading", { name: "欢迎使用 AGENTrader" })).toBeVisible()
  await page.getByRole("button", { name: "打开侧边栏" }).click()
  await expect(page.getByRole("dialog", { name: "AGENTrader" })).toBeVisible()
  await page.getByRole("link", { name: "任务中心" }).click()

  await expect(page).toHaveURL(/\/tasks/)
  await expect(page.getByRole("heading", { name: "任务中心" })).toBeVisible()
})

function mockApiPayload(path: string) {
  if (path.endsWith("/quote")) {
    return { symbol: "000001", name: "平安银行", market: "A股", price: 12.34, change_percent: 1.23, amount: 123456789, turnover_rate: 1.1, prev_close: 12.1, amplitude: 2.2, trade_date: "2026-06-04", updated_at: "2026-06-04T10:00:00Z" }
  }
  if (path.endsWith("/fundamentals")) {
    return { symbol: "000001", name: "平安银行", industry: "银行", sector: "金融", total_mv: 120000000000, pe_ttm: 6.5, pb_mrq: 0.8, roe: 11.2 }
  }
  if (path.endsWith("/kline")) {
    return { symbol: "000001", period: "day", limit: 120, adj: "none", items: [{ time: "2026-06-03", open: 12, close: 12.2, low: 11.9, high: 12.4 }, { time: "2026-06-04", open: 12.2, close: 12.34, low: 12.1, high: 12.5 }] }
  }
  if (path.endsWith("/news")) {
    return { symbol: "000001", days: 30, limit: 20, include_announcements: true, items: [{ title: "平安银行公告", source: "交易所", time: "2026-06-04", url: "#", type: "announcement" }] }
  }

  switch (path) {
    case "/api/health":
      return { ok: true }
    case "/api/analysis/tasks":
    case "/api/analysis/user/history":
      return { tasks: [], items: [], total: 0 }
    case "/api/reports/list":
      return {
        reports: [{ id: "r1", title: "贵州茅台 分析报告", stock_code: "600519", stock_name: "贵州茅台", status: "completed", type: "analysis", format: "markdown", created_at: "2026-01-01T00:00:00Z" }],
        total: 1
      }
    case "/api/reports/r1/detail":
      return { id: "r1", stock_symbol: "600519", stock_name: "贵州茅台", status: "completed", recommendation: "谨慎关注", summary: "## 摘要\n报告内容", reports: { market_report: "市场分析内容" }, created_at: "2026-01-01T00:00:00Z" }
    case "/api/usage/statistics":
      return { total_requests: 0, total_input_tokens: 0, total_output_tokens: 0, total_cost: 0, cost_by_currency: {}, by_provider: {}, by_model: {}, by_date: {} }
    case "/api/usage/records":
      return { records: [], total: 0 }
    case "/api/favorites/check/000001":
      return { symbol: "000001", is_favorite: false }
    case "/api/favorites/":
      return [{ symbol: "000001", stock_code: "000001", stock_name: "平安银行", market: "A股", tags: ["关注"], current_price: 12.34, change_percent: 1.23, added_at: "2026-06-04T10:00:00Z" }]
    case "/api/favorites/tags":
      return ["关注"]
    case "/api/sync/multi-source/sources/current":
      return { name: "tushare", priority: 1, description: "Tushare" }
    case "/api/screening/industries":
      return { industries: [{ value: "银行", label: "银行", count: 10 }], total: 1 }
    case "/api/screening/run":
      return { total: 1, items: [{ code: "000001", close: 12.34, pct_chg: 1.23, amount: 123456789, ma20: 12.1, rsi14: 55 }] }
    case "/api/paper/account":
      return { account: { cash: { CNY: 100000, HKD: 50000, USD: 10000 }, realized_pnl: { CNY: 0, HKD: 0, USD: 0 }, positions_value: { CNY: 1234, HKD: 0, USD: 0 }, equity: { CNY: 101234, HKD: 50000, USD: 10000 }, updated_at: "2026-06-04T10:00:00Z" }, positions: [] }
    case "/api/paper/positions":
    case "/api/paper/orders":
      return { items: [] }
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
      return [{ name: "default", type: "postgresql", host: "localhost", port: 5432, database: "agentrader", connection_params: {}, pool_size: 5, max_overflow: 10, enabled: true }]
    case "/api/config/settings":
      return { enable_cache: true, cache_ttl: 3600 }
    case "/api/config/model-catalog":
      return [{ provider: "dashscope", provider_name: "通义千问", models: [{ name: "qwen-turbo", display_name: "通义千问 Turbo" }] }]
    case "/api/system/database/status":
      return { postgres: { connected: true, host: "localhost", port: 5432, database: "agentrader", version: "15" }, redis: { connected: true, host: "localhost", port: 6379, database: 0, version: "7" } }
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
    case "/api/scheduler/jobs":
      return []
    case "/api/scheduler/stats":
      return { total_jobs: 0, running_jobs: 0, paused_jobs: 0, scheduler_running: true, scheduler_state: 1 }
    case "/api/scheduler/health":
      return { status: "healthy", running: true, state: 1, timestamp: new Date().toISOString() }
    case "/api/notifications/unread_count":
      return { count: 0 }
    case "/api/notifications":
      return { items: [], total: 0 }
    default:
      return {}
  }
}
