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
        data: { id: "admin", username: "admin", is_admin: true }
      })
    })
  })

  await page.route("**/api/health", async (route) => {
    await route.fulfill({ json: { success: true } })
  })

  await page.route("**/api/config/llm", async (route) => {
    await route.fulfill({
      json: {
        success: true,
        data: [
          {
            provider: "dashscope",
            model_name: "qwen-turbo",
            model_display_name: "Qwen Turbo",
            enabled: true,
            max_tokens: 8000,
            temperature: 0.7,
            timeout: 60,
            retry_times: 2
          },
          {
            provider: "dashscope",
            model_name: "qwen-max",
            model_display_name: "Qwen Max",
            enabled: true,
            max_tokens: 16000,
            temperature: 0.4,
            timeout: 60,
            retry_times: 2
          }
        ],
        message: "ok"
      }
    })
  })
})

test("submits single-stock configuration through direct Agent workflow metadata", async ({ page }) => {
  let sessionCreated = false
  let submittedBody: Record<string, unknown> | undefined

  await page.route("**/api/research-agent/live/status", async (route) => {
    await route.fulfill({ json: { success: true, data: { global_halted: false, brokers: [] } } })
  })
  await page.route("**/api/research-agent/sessions", async (route) => {
    if (route.request().method() === "GET") {
      await route.fulfill({
        json: {
          success: true,
          data: sessionCreated ? [{ session_id: "session-stock", title: "单股分析：600519" }] : []
        }
      })
      return
    }
    sessionCreated = true
    await route.fulfill({
      json: { success: true, data: { session_id: "session-stock", title: "单股分析：600519" } }
    })
  })
  await page.route("**/api/research-agent/sessions/session-stock/messages", async (route) => {
    if (route.request().method() === "GET") {
      const metadata = submittedBody?.metadata || {
        source: "research-agent-page",
        mode: "stock_analysis_workflow",
        tool_name: "stock_analysis",
        tool_arguments: {
          mode: "single",
          symbol: "600519",
          market_type: "A股",
          analysis_date: "2026-06-11",
          research_depth: "标准",
          selected_analysts: ["market", "fundamentals"],
          include_sentiment: true,
          include_risk: true,
          language: "zh-CN",
          quick_analysis_model: "qwen-turbo",
          deep_analysis_model: "qwen-max",
          custom_prompt: "",
          wait_for_completion: true,
          wait_timeout_seconds: 900
        }
      }
      await route.fulfill({
        json: {
          success: true,
          data: [
            {
              message_id: "user-stock",
              role: "user",
              content: "单股分析：600519 / A股 / 标准 / 市场+基本面 / 情绪+风险 / qwen-turbo -> qwen-max",
              linked_attempt_id: "attempt-stock",
              metadata
            },
            {
              message_id: "assistant-stock",
              role: "assistant",
              content: "单股分析任务已提交，任务 ID：task-600519",
              linked_attempt_id: "attempt-stock"
            }
          ]
        }
      })
      return
    }
    submittedBody = await route.request().postDataJSON()
    await route.fulfill({
      json: {
        success: true,
        data: {
          job_id: "job-stock",
          attempt_id: "attempt-stock",
          session_id: "session-stock"
        }
      }
    })
  })
  await page.route("**/api/research-agent/sessions/session-stock/attempts**", async (route) => {
    await route.fulfill({
      json: {
        success: true,
        data: [
          {
            attempt_id: "attempt-stock",
            status: "completed",
            result: { content: "单股分析任务已提交，任务 ID：task-600519" }
          }
        ]
      }
    })
  })
  await page.route("**/api/research-agent/sessions/session-stock/goal", async (route) => {
    await route.fulfill({ json: { success: true, data: null } })
  })
  await page.route("**/api/research-agent/sessions/session-stock/events**", async (route) => {
    if (!route.request().url().includes("/events/stream")) {
      await route.fulfill({
        json: {
          success: true,
          data: [
            {
              event_id: 1,
              event_type: "stock_analysis.stage",
              payload: {
                attempt_id: "attempt-stock",
                tool_name: "stock_analysis",
                mode: "single",
                stage: "analysis_task",
                title: "单股分析任务",
                status: "running",
                task_id: "task-600519",
                report_url: "/reports/view/task-600519",
                message: "任务已入队",
                progress: 15
              }
            }
          ]
        }
      })
      return
    }
    await new Promise((resolve) => setTimeout(resolve, 100))
    await route.fulfill({
      headers: { "Content-Type": "text/event-stream" },
      body:
        "event: stock_analysis.stage\n" +
        "data: {\"attempt_id\":\"attempt-stock\",\"tool_name\":\"stock_analysis\",\"mode\":\"single\",\"stage\":\"analysis_task\",\"title\":\"单股分析任务\",\"status\":\"running\",\"task_id\":\"task-600519\",\"report_url\":\"/reports/view/task-600519\",\"message\":\"任务已入队\",\"progress\":15}\n\n" +
        "event: message_completed\n" +
        "data: {\"attempt_id\":\"attempt-stock\",\"content\":\"单股分析任务已提交，任务 ID：task-600519\"}\n\n" +
        "event: attempt.completed\n" +
        "data: {\"attempt_id\":\"attempt-stock\",\"session_id\":\"session-stock\",\"content\":\"单股分析任务已提交，任务 ID：task-600519\"}\n\n"
    })
  })

  await page.goto("/agent")
  await page.getByRole("button", { name: "更多选项" }).click()
  await page.getByRole("button", { name: "单股分析" }).click()
  await page.getByLabel("股票代码").fill("600519")
  await page.getByRole("button", { name: /开始分析/ }).click()

  await expect.poll(() => submittedBody).toBeTruthy()
  const metadata = submittedBody?.metadata as Record<string, unknown>
  const argumentsPayload = metadata.tool_arguments as Record<string, unknown>
  expect(metadata.mode).toBe("stock_analysis_workflow")
  expect(metadata.tool_name).toBe("stock_analysis")
  expect(argumentsPayload).toMatchObject({
    mode: "single",
    symbol: "600519",
    market_type: "A股",
    research_depth: "标准",
    selected_analysts: ["market", "fundamentals"],
    include_sentiment: true,
    include_risk: true,
    quick_analysis_model: "qwen-turbo",
    deep_analysis_model: "qwen-max",
    wait_for_completion: true,
    wait_timeout_seconds: 900
  })

  await expect(page.getByText("已提交，执行步骤和报告链接会在右侧更新。")).toBeVisible()
})

test("restores persisted single-stock stage events into the right rail", async ({ page }) => {
  await page.route("**/api/research-agent/live/status", async (route) => {
    await route.fulfill({ json: { success: true, data: { global_halted: false, brokers: [] } } })
  })
  await page.route("**/api/research-agent/sessions", async (route) => {
    await route.fulfill({
      json: {
        success: true,
        data: [{ session_id: "session-stock", title: "单股分析：600519" }]
      }
    })
  })
  await page.route("**/api/research-agent/sessions/session-stock/messages", async (route) => {
    await route.fulfill({
      json: {
        success: true,
        data: [
          {
            message_id: "user-stock",
            role: "user",
            content: "单股分析：600519 / A股 / 标准 / 市场+基本面 / 情绪+风险 / qwen-turbo -> qwen-max",
            linked_attempt_id: "attempt-stock",
            metadata: {
              source: "research-agent-page",
              mode: "stock_analysis_workflow",
              tool_name: "stock_analysis",
              tool_arguments: {
                mode: "single",
                symbol: "600519",
                market_type: "A股",
                analysis_date: "2026-06-11",
                research_depth: "标准",
                selected_analysts: ["market", "fundamentals"],
                include_sentiment: true,
                include_risk: true,
                language: "zh-CN",
                quick_analysis_model: "qwen-turbo",
                deep_analysis_model: "qwen-max",
                custom_prompt: "",
                wait_for_completion: true,
                wait_timeout_seconds: 900
              }
            }
          },
          {
            message_id: "assistant-stock",
            role: "assistant",
            content: "单股分析任务已提交，任务 ID：task-600519",
            linked_attempt_id: "attempt-stock"
          }
        ]
      }
    })
  })
  await page.route("**/api/research-agent/sessions/session-stock/events**", async (route) => {
    await route.fulfill({
      json: {
        success: true,
        data: [
          {
            event_id: 1,
            event_type: "stock_analysis.stage",
            payload: {
              attempt_id: "attempt-stock",
              tool_name: "stock_analysis",
              mode: "single",
              stage: "analysis_task",
              title: "单股分析任务",
              status: "running",
              task_id: "task-600519",
              report_url: "/reports/view/task-600519",
              message: "任务已入队",
              progress: 15
            }
          }
        ]
      }
    })
  })
  await page.route("**/api/research-agent/sessions/session-stock/goal", async (route) => {
    await route.fulfill({ json: { success: true, data: null } })
  })
  await page.route("**/api/research-agent/sessions/session-stock/attempts**", async (route) => {
    await route.fulfill({ json: { success: true, data: [] } })
  })

  await page.goto("/agent")

  await expect(page.getByRole("button", { name: /单股分析任务/ })).toBeVisible()
  await expect(page.getByText("任务：task-600519")).toBeVisible()
  await expect(page.getByRole("link", { name: /查看任务/ })).toHaveAttribute("href", "/tasks?task_id=task-600519")
  await expect(page.getByRole("link", { name: /查看报告/ })).toHaveAttribute("href", "/reports/view/task-600519")
})
