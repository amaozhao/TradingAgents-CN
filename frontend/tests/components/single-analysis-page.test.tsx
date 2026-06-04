import { render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

import { SingleAnalysisPage } from "@/features/analysis/single-analysis-page"

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: vi.fn()
  })
}))

vi.mock("@/libs/api/analysis", () => ({
  analysisApi: {
    startSingleAnalysis: vi.fn()
  }
}))

describe("SingleAnalysisPage", () => {
  it("uses the app date picker instead of the browser native date input", () => {
    render(<SingleAnalysisPage />)

    const dateControl = screen.getByLabelText("分析日期")

    expect(dateControl.tagName).toBe("BUTTON")
    expect(dateControl).not.toHaveAttribute("type", "date")
  })
})
