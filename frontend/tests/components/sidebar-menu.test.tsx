import { render, screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { SidebarMenu } from "@/components/layout/sidebar-menu"

let pathname = "/dashboard"
let search = ""

vi.mock("next/navigation", () => ({
  usePathname: () => pathname,
  useSearchParams: () => new URLSearchParams(search)
}))

describe("SidebarMenu", () => {
  beforeEach(() => {
    pathname = "/dashboard"
    search = ""
  })

  it("expands only the active analysis group", () => {
    pathname = "/analysis/batch"

    render(<SidebarMenu collapsed={false} />)

    const nav = screen.getByRole("navigation")
    expect(within(nav).getByRole("link", { name: "批量分析" })).toBeInTheDocument()
    expect(within(nav).queryByRole("link", { name: "配置管理" })).not.toBeInTheDocument()
  })

  it("keeps inactive group headers available as navigation links", () => {
    pathname = "/dashboard"

    render(<SidebarMenu collapsed={false} />)

    const nav = screen.getByRole("navigation")
    expect(within(nav).getByRole("link", { name: "股票分析" })).toHaveAttribute("href", "/analysis/single")
    expect(within(nav).getByRole("link", { name: "设置" })).toHaveAttribute("href", "/settings")
    expect(within(nav).queryByRole("link", { name: "批量分析" })).not.toBeInTheDocument()
    expect(within(nav).queryByRole("link", { name: "配置管理" })).not.toBeInTheDocument()
  })

  it("expands only the active settings group", () => {
    pathname = "/settings/config"

    render(<SidebarMenu collapsed={false} />)

    const nav = screen.getByRole("navigation")
    expect(within(nav).getByRole("link", { name: "系统配置" })).toHaveClass("bg-sidebar-accent")
    expect(within(nav).queryByRole("link", { name: "批量分析" })).not.toBeInTheDocument()
    expect(within(nav).queryByRole("link", { name: "外观设置" })).not.toBeInTheDocument()
    expect(within(nav).queryByRole("link", { name: "配置管理" })).not.toBeInTheDocument()
  })

  it("shows only settings category entries on the default settings page", () => {
    pathname = "/settings"

    render(<SidebarMenu collapsed={false} />)

    const nav = screen.getByRole("navigation")
    expect(within(nav).getByText("个人设置")).toBeInTheDocument()
    expect(within(nav).getByText("系统配置")).toBeInTheDocument()
    expect(within(nav).getByText("系统管理")).toBeInTheDocument()
    expect(within(nav).queryByRole("link", { name: "通用设置" })).not.toBeInTheDocument()
    expect(within(nav).queryByRole("link", { name: "外观设置" })).not.toBeInTheDocument()
  })

  it("keeps settings categories visible after clicking personal settings", async () => {
    const user = userEvent.setup()
    pathname = "/settings"

    render(<SidebarMenu collapsed={false} onNavigate={(event) => event?.preventDefault()} />)

    const nav = screen.getByRole("navigation")
    expect(within(nav).getByRole("link", { name: "个人设置" })).toHaveAttribute("href", "/settings")

    await user.click(within(nav).getByRole("link", { name: "个人设置" }))

    expect(within(nav).getByRole("link", { name: "个人设置" })).toBeInTheDocument()
    expect(within(nav).getByRole("link", { name: "系统配置" })).toBeInTheDocument()
    expect(within(nav).queryByRole("link", { name: "安全设置" })).not.toBeInTheDocument()
  })

  it("highlights personal settings when a personal tab is active", () => {
    pathname = "/settings"
    search = "tab=appearance"

    render(<SidebarMenu collapsed={false} />)

    const nav = screen.getByRole("navigation")
    expect(within(nav).getByRole("link", { name: "个人设置" })).toHaveClass("bg-sidebar-accent")
    expect(within(nav).queryByRole("link", { name: "外观设置" })).not.toBeInTheDocument()
    expect(within(nav).queryByRole("link", { name: "配置管理" })).not.toBeInTheDocument()
  })

  it("highlights the matching settings category for hidden settings routes", () => {
    pathname = "/settings/scheduler"

    render(<SidebarMenu collapsed={false} />)

    const nav = screen.getByRole("navigation")
    expect(within(nav).getByRole("link", { name: "系统管理" })).toHaveClass("bg-sidebar-accent")
    expect(within(nav).getByRole("link", { name: "个人设置" })).not.toHaveClass("bg-sidebar-accent")
    expect(within(nav).queryByRole("link", { name: "定时任务" })).not.toBeInTheDocument()
  })
})
