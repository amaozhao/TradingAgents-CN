import { render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

import { MarkdownRenderer } from "@/features/learning/markdown-renderer"

vi.mock("@/features/learning/mermaid-renderer", () => ({
  MermaidRenderer: ({ chart }: { chart: string }) => (
    <div data-testid="mermaid-chart">{chart}</div>
  )
}))

describe("MarkdownRenderer", () => {
  it("renders mermaid fenced code blocks with the Mermaid renderer", () => {
    render(
      <MarkdownRenderer
        content={`## 流程

\`\`\`mermaid
graph TD
  A[开始] --> B[结束]
\`\`\`

正文继续`}
      />
    )

    expect(screen.getByRole("heading", { name: "流程" })).toBeInTheDocument()
    expect(screen.getByTestId("mermaid-chart")).toHaveTextContent("A[开始] --> B[结束]")
    expect(screen.queryByText("graph TD")).not.toBeInTheDocument()
  })

  it("wraps markdown tables in a local horizontal scroll container", () => {
    const { container } = render(
      <MarkdownRenderer
        content={[
          "| Greek | Call | Put | 含义 | 风险/对冲含义 |",
          "|---|---:|---:|---|---|",
          "| Delta | +0.3930 | -0.6070 | 标的价格变动 1 元 | 卖方对冲 1 张 Call |"
        ].join("\n")}
      />
    )

    const scrollContainer = container.querySelector(".markdown-table-scroll")
    expect(scrollContainer).not.toBeNull()
    expect(scrollContainer?.querySelector("table")).toBe(screen.getByRole("table"))
  })
})
