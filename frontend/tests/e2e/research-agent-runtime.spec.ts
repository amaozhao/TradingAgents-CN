import { expect, test } from "@playwright/test"

import { installNotificationMocks } from "./helpers"

test.beforeEach(async ({ page }) => {
  await installNotificationMocks(page)
  await page.addInitScript(() => {
    window.localStorage.setItem("auth-token", "access.payload.sig")
    window.localStorage.setItem("refresh-token", "refresh.payload.sig")
    window.localStorage.setItem("user-info", JSON.stringify({ username: "admin" }))
    window.localStorage.setItem("config-wizard-completed", "true")
  })

  await page.route("**/api/auth/me", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        success: true,
        data: { id: "admin", username: "admin", is_admin: true },
      }),
    })
  })

  await page.route("**/api/research-agent/sessions", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([]),
    })
  })
})

test("agent page exposes the current-project Agent runtime capability surface", async ({ page }) => {
  await page.goto("/agent")

  await expect(page.getByRole("heading", { name: "Agent" }).first()).toBeVisible()
  await expect(page.getByText("跨市场组合回测")).toBeVisible()
  await expect(page.getByText("运行时与连接器")).toBeVisible()
  await expect(page.getByText("检查交易连接器")).toBeVisible()
  await expect(page.getByText("Shadow Account").first()).toBeVisible()
  await expect(page.getByText("智能体团队").first()).toBeVisible()
})
