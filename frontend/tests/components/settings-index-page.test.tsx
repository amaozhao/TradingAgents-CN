import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { SettingsIndexPage } from "@/features/settings/settings-pages"

const replace = vi.fn()
let search = ""

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace }),
  useSearchParams: () => new URLSearchParams(search)
}))

describe("SettingsIndexPage", () => {
  beforeEach(() => {
    replace.mockClear()
    search = ""
  })

  it("shows general settings by default", () => {
    render(<SettingsIndexPage />)

    expect(screen.getByRole("tab", { name: "通用设置" })).toHaveAttribute("data-state", "active")
    expect(screen.getByText("用户名")).toBeInTheDocument()
    expect(screen.getByText("邮箱")).toBeInTheDocument()
    expect(screen.getByText("时区")).toBeInTheDocument()
  })

  it("opens the personal settings tab from the URL query", () => {
    search = "tab=appearance"

    render(<SettingsIndexPage />)

    expect(screen.getByRole("tab", { name: "外观设置" })).toHaveAttribute("data-state", "active")
    expect(screen.getByText("主题模式")).toBeInTheDocument()
  })

  it("updates the URL when a personal settings tab is selected", async () => {
    const user = userEvent.setup()

    render(<SettingsIndexPage />)

    await user.click(screen.getByRole("tab", { name: "通知设置" }))

    expect(replace).toHaveBeenCalledWith("/settings?tab=notifications")
  })
})
