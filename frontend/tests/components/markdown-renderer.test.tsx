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
})
