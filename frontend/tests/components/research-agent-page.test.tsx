import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"

import { ResearchAgentPage } from "@/features/research-agent/research-agent-page"

describe("ResearchAgentPage", () => {
  it("renders the agent workspace areas", () => {
    render(<ResearchAgentPage />)

    expect(screen.getByText("研究 Agent")).toBeInTheDocument()
    expect(screen.getByText("会话列表")).toBeInTheDocument()
    expect(screen.getByText("消息时间线")).toBeInTheDocument()
    expect(screen.getByText("工具时间线")).toBeInTheDocument()
    expect(screen.getByText("产物抽屉")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "取消" })).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "重试" })).toBeInTheDocument()
    expect(screen.getByText("最终报告")).toBeInTheDocument()
  })
})
