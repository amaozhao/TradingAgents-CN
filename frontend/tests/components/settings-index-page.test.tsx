import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { render, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { SettingsIndexPage } from "@/features/settings/settings-pages"
import { authApi } from "@/libs/api/auth"

const replace = vi.fn()
let search = ""

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace }),
  useSearchParams: () => new URLSearchParams(search)
}))

vi.mock("@/libs/api/auth", () => ({
  authApi: {
    changePassword: vi.fn()
  }
}))

function renderWithQueryClient(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: {
      mutations: { retry: false },
      queries: { retry: false }
    }
  })

  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>)
}

describe("SettingsIndexPage", () => {
  beforeEach(() => {
    replace.mockClear()
    search = ""
    vi.mocked(authApi.changePassword).mockResolvedValue({ success: true, data: {}, message: "ok" })
  })

  it("shows general settings by default", () => {
    renderWithQueryClient(<SettingsIndexPage />)

    expect(screen.getByRole("tab", { name: "通用设置" })).toHaveAttribute("data-state", "active")
    expect(screen.getByText("用户名")).toBeInTheDocument()
    expect(screen.getByText("邮箱")).toBeInTheDocument()
    expect(screen.getByText("时区")).toBeInTheDocument()
  })

  it("opens the personal settings tab from the URL query", () => {
    search = "tab=appearance"

    renderWithQueryClient(<SettingsIndexPage />)

    expect(screen.getByRole("tab", { name: "外观设置" })).toHaveAttribute("data-state", "active")
    expect(screen.getByText("主题模式")).toBeInTheDocument()
  })

  it("updates the URL when a personal settings tab is selected", async () => {
    const user = userEvent.setup()

    renderWithQueryClient(<SettingsIndexPage />)

    await user.click(screen.getByRole("tab", { name: "通知设置" }))

    expect(replace).toHaveBeenCalledWith("/settings?tab=notifications")
  })

  it("submits the change password dialog through the account API", async () => {
    search = "tab=security"
    const user = userEvent.setup()

    renderWithQueryClient(<SettingsIndexPage />)

    await user.click(screen.getByRole("button", { name: "修改密码" }))
    const dialog = screen.getByRole("dialog", { name: "修改密码" })
    await user.type(within(dialog).getByLabelText("当前密码"), "old-pass")
    await user.type(within(dialog).getByLabelText("新密码"), "new-pass-123")
    await user.type(within(dialog).getByLabelText("确认新密码"), "new-pass-123")
    await user.click(within(dialog).getByRole("button", { name: "保存" }))

    await waitFor(() =>
      expect(authApi.changePassword).toHaveBeenCalledWith({
        old_password: "old-pass",
        new_password: "new-pass-123",
        confirm_password: "new-pass-123"
      })
    )
  })
})
