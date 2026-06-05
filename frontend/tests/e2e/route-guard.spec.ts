import { expect, test } from "@playwright/test"
import { installNotificationMocks } from "./helpers"

test.beforeEach(async ({ page }) => {
  await installNotificationMocks(page)
  await page.route("**/api/health", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ success: true }) })
  })
  await page.route("**/api/analysis/user/history**", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ success: true, data: { items: [] }, message: "ok" }) })
  })
  await page.route("**/api/favorites/**", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ success: true, data: [], message: "ok" }) })
  })
  await page.route("**/api/news-data/latest**", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ success: true, data: { news: [] }, message: "ok" }) })
  })
  await page.route("**/api/paper/account", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ success: true, data: { account: null }, message: "ok" }) })
  })
})

test("redirects an unauthenticated protected route to login", async ({ page }) => {
  await page.goto("/dashboard")

  await expect(page).toHaveURL(/\/login/)
  await expect(page.getByRole("heading", { name: "AGENTrader" })).toBeVisible()
})

test("redirects an authenticated login visit to dashboard", async ({ page }) => {
  await page.addInitScript(() => {
    window.localStorage.setItem("auth-token", "access.payload.sig")
    window.localStorage.setItem("refresh-token", "refresh.payload.sig")
    window.localStorage.setItem("user-info", JSON.stringify({ username: "admin" }))
    window.localStorage.setItem("config-wizard-completed", "true")
  })

  await page.goto("/login")

  await expect(page).toHaveURL(/\/dashboard/)
  await expect(page.getByRole("heading", { name: "欢迎使用 AGENTrader" })).toBeVisible()
})

test("logs in and redirects to dashboard", async ({ page }) => {
  await page.addInitScript(() => {
    window.localStorage.setItem("config-wizard-completed", "true")
  })
  await page.route("**/api/auth/login", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        success: true,
        message: "ok",
        data: {
          access_token: "access.payload.sig",
          refresh_token: "refresh.payload.sig",
          token_type: "bearer",
          expires_in: 3600,
          user: { username: "admin", email: "admin@example.com" }
        }
      })
    })
  })

  await page.goto("/login")
  await page.getByPlaceholder("请输入用户名").fill("admin")
  await page.getByPlaceholder("请输入密码").fill("admin123")
  await page.getByRole("button", { name: "登录" }).click()

  await expect(page).toHaveURL(/\/dashboard/)
  await expect(page.getByRole("heading", { name: "欢迎使用 AGENTrader" })).toBeVisible()
  await expect(page.evaluate(() => window.localStorage.getItem("auth-token"))).resolves.toBe("access.payload.sig")
})
