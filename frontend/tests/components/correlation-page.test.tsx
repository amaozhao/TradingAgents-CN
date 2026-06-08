import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"

import { CorrelationPage } from "@/features/research-matrix/correlation-page"

describe("CorrelationPage", () => {
  it("renders universe controls, heatmap, and candidate lists", () => {
    render(<CorrelationPage />)

    expect(screen.getByText("相关性矩阵")).toBeInTheDocument()
    expect(screen.getByText("Universe Selector")).toBeInTheDocument()
    expect(screen.getByText("日期范围")).toBeInTheDocument()
    expect(screen.getByText("窗口")).toBeInTheDocument()
    expect(screen.getByText("方法")).toBeInTheDocument()
    expect(screen.getByText("Heatmap")).toBeInTheDocument()
    expect(screen.getByText("高相关组合")).toBeInTheDocument()
    expect(screen.getByText("分散候选")).toBeInTheDocument()
  })
})
