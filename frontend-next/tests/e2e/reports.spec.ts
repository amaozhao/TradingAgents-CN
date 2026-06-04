import { expect, test } from "@playwright/test"

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    window.localStorage.setItem("auth-token", "access.payload.sig")
    window.localStorage.setItem("refresh-token", "refresh.payload.sig")
    window.localStorage.setItem("user-info", JSON.stringify({ username: "admin" }))
    window.localStorage.setItem("config-wizard-completed", "true")
  })
  await page.route("**/api/health", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ success: true }) })
  })
  await page.route("**/api/reports/list**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        success: true,
        data: {
          reports: [{ id: "r1", title: "贵州茅台 分析报告", stock_code: "600519", stock_name: "贵州茅台", status: "completed", type: "analysis", format: "markdown", created_at: "2026-01-01T00:00:00Z" }],
          total: 1
        }
      })
    })
  })
  await page.route("**/api/reports/r1/detail", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        success: true,
        data: {
          id: "r1",
          stock_symbol: "600519",
          stock_name: "贵州茅台",
          status: "completed",
          recommendation: "谨慎关注",
          summary: "## 摘要\\n报告内容",
          reports: { market_report: "市场分析内容" },
          created_at: "2026-01-01T00:00:00Z"
        }
      })
    })
  })
})

test("opens reports list and detail route", async ({ page }) => {
  await page.goto("/reports")
  await expect(page.getByRole("heading", { name: "分析报告" })).toBeVisible()
  await expect(page.getByText("贵州茅台 分析报告")).toBeVisible()

  await page.getByRole("link", { name: "贵州茅台 分析报告" }).click()
  await expect(page).toHaveURL(/\/reports\/view\/r1/)
  await expect(page.getByRole("heading", { name: "贵州茅台 分析报告" })).toBeVisible()
  await expect(page.getByText("市场分析内容")).toBeVisible()
})
