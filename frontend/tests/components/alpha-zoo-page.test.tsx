import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"

import { AlphaZooPage } from "@/features/alpha-zoo/alpha-zoo-page"

describe("AlphaZooPage", () => {
  it("renders filters, factor table, detail, and bench runner", () => {
    render(<AlphaZooPage />)

    expect(screen.getByText("Alpha Zoo")).toBeInTheDocument()
    expect(screen.getByText("因子筛选")).toBeInTheDocument()
    expect(screen.getByText("因子表")).toBeInTheDocument()
    expect(screen.getByText("因子详情")).toBeInTheDocument()
    expect(screen.getByText("Bench Runner")).toBeInTheDocument()
    expect(screen.getByText("IC/IR 摘要")).toBeInTheDocument()
    expect(screen.getByText("发送到 Agent")).toBeInTheDocument()
  })
})
