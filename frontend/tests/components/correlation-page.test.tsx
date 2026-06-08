import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"

import { CorrelationPage } from "@/features/research-matrix/correlation-page"

describe("CorrelationPage", () => {
  it("renders source-style controls and chart placeholder", () => {
    render(<CorrelationPage />)

    expect(screen.getByText("相关性矩阵")).toBeInTheDocument()
    expect(screen.getByText("资产代码")).toBeInTheDocument()
    expect(screen.getByText("窗口（天）")).toBeInTheDocument()
    expect(screen.getByText("方法")).toBeInTheDocument()
    expect(screen.getByText("计算")).toBeInTheDocument()
    expect(screen.getByText("暂无相关性数据")).toBeInTheDocument()
  })
})
