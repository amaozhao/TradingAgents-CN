import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"

import { AlphaZooPage } from "@/features/alpha-zoo/alpha-zoo-page"

describe("AlphaZooPage", () => {
  it("renders source-style hero, zoo cards, filters, and catalogue", () => {
    render(<AlphaZooPage />)

    expect(screen.getByText("Alpha 因子库")).toBeInTheDocument()
    expect(screen.getByText("ALPHA ZOO")).toBeInTheDocument()
    expect(screen.getByText("452 个预置量化 Alpha，覆盖 4 个因子库")).toBeInTheDocument()
    expect(screen.getByText("Qlib 158")).toBeInTheDocument()
    expect(screen.getByText("GTJA 191")).toBeInTheDocument()
    expect(screen.getByText("搜索")).toBeInTheDocument()
    expect(screen.getByText("Alpha 因子目录")).toBeInTheDocument()
    expect(screen.getByText("运行基准测试")).toBeInTheDocument()
  })
})
