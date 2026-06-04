import { expect, test } from "@playwright/test"

test("redirects an unauthenticated protected route to login", async ({ page }) => {
  await page.goto("/dashboard")

  await expect(page).toHaveURL(/\/login/)
  await expect(page.getByRole("heading", { name: "登录" })).toBeVisible()
})

test("redirects an authenticated login visit to dashboard", async ({ page }) => {
  await page.addInitScript(() => {
    window.localStorage.setItem("auth-token", "access.payload.sig")
    window.localStorage.setItem("refresh-token", "refresh.payload.sig")
    window.localStorage.setItem("user-info", JSON.stringify({ username: "admin" }))
  })

  await page.goto("/login")

  await expect(page).toHaveURL(/\/dashboard/)
  await expect(page.getByRole("heading", { name: "仪表板" })).toBeVisible()
})
