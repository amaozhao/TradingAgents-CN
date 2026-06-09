import { expect, test } from "@playwright/test"

import { installNotificationMocks } from "./helpers"

const realAgentEnabled = process.env.E2E_REAL_AGENT === "1"
const authToken = process.env.E2E_AUTH_TOKEN || ""

test.describe("real Agent chat flow", () => {
  test.skip(!realAgentEnabled, "Set E2E_REAL_AGENT=1 to run the live Agent E2E flow")
  test.skip(!authToken, "Set E2E_AUTH_TOKEN to a valid backend JWT")
  test.setTimeout(180_000)

  test.beforeEach(async ({ page }) => {
    await installNotificationMocks(page)
    await page.addInitScript((token) => {
      window.localStorage.setItem("auth-token", token)
      window.localStorage.setItem("refresh-token", token)
      window.localStorage.setItem("user-info", JSON.stringify({ username: "admin", is_admin: true }))
      window.localStorage.setItem("config-wizard-completed", "true")
    }, authToken)
  })

  test("creates a session, runs connector tools, and renders the final assistant answer", async ({ page }) => {
    await page.goto("/agent")

    await page.getByRole("button", { name: /^新会话$/ }).last().click()
    await page.locator("textarea").fill("请检查交易连接器 profiles 和当前连接器状态，不要下单。最后用一句话总结是否可用。")

    await expect(page.getByRole("button", { name: "发送" })).toBeEnabled()
    await page.getByRole("button", { name: "发送" }).click()

    await expect(page.getByText("智能体正在工作...")).toBeVisible({ timeout: 15_000 })
    await expect(page.getByText("交易连接器列表")).toBeVisible({ timeout: 90_000 })
    await expect(page.getByText("交易连接器检查")).toBeVisible({ timeout: 90_000 })
    await expect(page.getByText("config_required").first()).toBeVisible({ timeout: 120_000 })
    await expect(page.getByText("智能体正在工作...")).toHaveCount(0)

    const renderedAnswers = page.getByTestId("agent-message-answer")
    await expect(renderedAnswers.last()).toContainText("paper")
    await expect(renderedAnswers.last()).toContainText("config_required")
    await expect(renderedAnswers.last()).toContainText("下单")
  })
})
