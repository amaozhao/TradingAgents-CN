import { render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

import { Breadcrumb } from "@/components/layout/breadcrumb"

const mockPathname = vi.fn()

vi.mock("next/navigation", () => ({
  usePathname: () => mockPathname()
}))

describe("Breadcrumb", () => {
  it("hides technical route segments on report detail pages", () => {
    mockPathname.mockReturnValue("/reports/view/7764104000574a8b82130b86")

    render(<Breadcrumb />)

    expect(screen.getByRole("link", { name: "分析报告" })).toHaveAttribute("href", "/reports")
    expect(screen.getByText("报告详情")).toBeInTheDocument()
    expect(screen.queryByText("view")).not.toBeInTheDocument()
  })
})
