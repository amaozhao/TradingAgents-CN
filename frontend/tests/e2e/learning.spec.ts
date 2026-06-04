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
  await page.route("**/api/health", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ success: true, data: { ok: true } }) })
  })
})

test("opens learning article, preserves paper redirect, and opens about", async ({ page }) => {
  await page.goto("/learning")
  await expect(page.getByRole("heading", { name: "学习中心" })).toBeVisible()

  await page.goto("/learning/article/what-is-llm")
  await expect(page.getByRole("heading", { name: "什么是大语言模型（LLM）？" }).first()).toBeVisible()
  await expect(page.getByText("学习目标")).toBeVisible()

  await page.goto("/paper/TradingAgents_论文中文版.md")
  await expect(page).toHaveURL(/\/learning\/article\/TradingAgents_/)
  await expect(page.getByRole("heading", { name: "TradingAgents 论文中文版" }).first()).toBeVisible()

  await page.goto("/about")
  await expect(page.getByRole("heading", { name: "TradingAgents-CN" }).first()).toBeVisible()
  await expect(page.getByText("核心功能")).toBeVisible()
})
