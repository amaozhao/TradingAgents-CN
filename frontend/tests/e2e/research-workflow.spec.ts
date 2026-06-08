import { expect, test } from "@playwright/test"

import { installNotificationMocks } from "./helpers"

test.beforeEach(async ({ page }) => {
  let sessionCreated = false
  const persistedEvents = [
    {
      event_id: 1,
      event_type: "assistant_delta",
      payload: { content: "储能板块分析进行中" }
    },
    {
      event_id: 2,
      event_type: "tool_completed",
      payload: { tool_name: "alpha_bench", artifact_id: "artifact-alpha-a" }
    },
    {
      event_id: 3,
      event_type: "message_completed",
      payload: { content: "推荐个股：300750.SZ，理由见关联报告。" }
    }
  ]

  await installNotificationMocks(page)
  await page.addInitScript(() => {
    window.localStorage.setItem("auth-token", "access.payload.sig")
    window.localStorage.setItem("refresh-token", "refresh.payload.sig")
    window.localStorage.setItem("user-info", JSON.stringify({ username: "admin" }))
    window.localStorage.setItem("config-wizard-completed", "true")
  })
  await page.route("**/api/health", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ success: true })
    })
  })
  await page.route("**/api/research-agent/sessions", route => {
    if (route.request().method() === "GET") {
      return route.fulfill({
        json: {
          success: true,
          data: sessionCreated ? [{ session_id: "session-a", title: "储能板块分析" }] : []
        }
      })
    }
    sessionCreated = true
    return route.fulfill({
      json: { success: true, data: { session_id: "session-a", title: "储能板块分析" } },
    })
  })

  await page.route("**/api/research-agent/sessions/session-a/messages", route => {
    if (route.request().method() === "GET") {
      return route.fulfill({ json: { success: true, data: [] } })
    }

    return route.fulfill({
      json: { success: true, data: { task_id: "research-task-a" } },
    })
  })

  await page.route("**/api/research-agent/sessions/session-a/events**", route => {
    if (!route.request().headers().accept?.includes("text/event-stream")) {
      return route.fulfill({ json: { success: true, data: persistedEvents } })
    }

    return route.fulfill({
      body:
        "event: assistant_delta\n" +
        "data: {\"content\":\"储能板块分析进行中\"}\n\n" +
        "event: tool_completed\n" +
        "data: {\"tool_name\":\"alpha_bench\",\"artifact_id\":\"artifact-alpha-a\"}\n\n" +
        "event: message_completed\n" +
        "data: {\"content\":\"推荐个股：300750.SZ，理由见关联报告。\"}\n\n",
      headers: { "Content-Type": "text/event-stream" },
    })
  })
})

test("completes storage-sector research workflow and restores final output", async ({ page }) => {
  await page.goto("/agent")

  await page.getByLabel("研究提示").fill("分析储能板块，筛选有 Alpha 证据的候选股")
  await page.getByRole("button", { name: "发送" }).click()

  await expect(page.getByText("储能板块分析进行中")).toBeVisible()
  const toolTimeline = page.getByRole("region", { name: "工具时间线" })
  await expect(toolTimeline.getByText("alpha_bench")).toBeVisible()
  await expect(toolTimeline.getByText("artifact-alpha-a")).toBeVisible()

  const finalReport = page.getByRole("region", { name: "最终报告" })
  await expect(finalReport).toContainText("推荐个股：300750.SZ，理由见关联报告。")

  await page.reload()
  await expect(page.getByRole("region", { name: "最终报告" })).toContainText(
    "推荐个股：300750.SZ，理由见关联报告。"
  )
  const restoredToolTimeline = page.getByRole("region", { name: "工具时间线" })
  await expect(restoredToolTimeline.getByText("alpha_bench")).toBeVisible()
  await expect(restoredToolTimeline.getByText("artifact-alpha-a")).toBeVisible()
  await expect(page.getByText("artifact-alpha-a")).toHaveCount(2)
})
