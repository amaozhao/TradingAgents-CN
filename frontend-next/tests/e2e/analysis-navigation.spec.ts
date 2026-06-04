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
  await page.route("**/api/analysis/tasks**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        success: true,
        data: { tasks: [], total: 0 },
        message: "ok"
      })
    })
  })
})

test("opens single and batch analysis pages", async ({ page }) => {
  await page.goto("/analysis/single")
  await expect(page.getByRole("heading", { name: "单股分析" })).toBeVisible()
  await expect(page.getByLabel("股票代码")).toBeVisible()

  await page.goto("/analysis/batch")
  await expect(page.getByRole("heading", { name: "批量分析" })).toBeVisible()
  await expect(page.getByLabel("股票代码列表")).toBeVisible()
})

test("opens the completed task tab from history redirect", async ({ page }) => {
  await page.goto("/analysis/history")

  await expect(page).toHaveURL(/\/tasks\?tab=completed/)
  await expect(page.getByRole("heading", { name: "任务中心" })).toBeVisible()
  await expect(page.getByRole("tab", { name: "已完成" })).toHaveAttribute("data-state", "active")
})
