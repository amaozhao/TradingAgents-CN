import { render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

import { SingleAnalysisPage } from "@/features/analysis/single-analysis-page"

let search = ""

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: vi.fn()
  }),
  useSearchParams: () => new URLSearchParams(search)
}))

vi.mock("@/libs/api/analysis", () => ({
  analysisApi: {
    startSingleAnalysis: vi.fn()
  }
}))

describe("SingleAnalysisPage", () => {
  beforeEach(() => {
    search = ""
  })

  it("uses the app date picker instead of the browser native date input", () => {
    render(<SingleAnalysisPage />)

    const dateControl = screen.getByLabelText("分析日期")

    expect(dateControl.tagName).toBe("BUTTON")
    expect(dateControl).not.toHaveAttribute("type", "date")
  })

  it("prefills the stock symbol from the URL query", () => {
    search = "symbol=600519"

    render(<SingleAnalysisPage />)

    expect(screen.getByLabelText("股票代码")).toHaveValue("600519")
  })
})
