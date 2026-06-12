import { render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

import { BatchConfigCard } from "@/features/research/batch"
import { configApi } from "@/libs/api/config"

vi.mock("@/libs/api/config", () => ({
  configApi: {
    getLLMConfigs: vi.fn()
  }
}))

describe("BatchConfigCard", () => {
  it("allows long model selectors to shrink inside the responsive batch grid", async () => {
    vi.mocked(configApi.getLLMConfigs).mockResolvedValue([
      {
        provider: "minimax",
        model_name: "MiniMax-M3",
        model_display_name: "MiniMax-M3",
        enabled: true,
        max_tokens: 8000,
        temperature: 0.7,
        timeout: 60,
        retry_times: 2
      }
    ])

    render(
      <BatchConfigCard
        running={false}
        onCancel={vi.fn()}
        onSave={vi.fn()}
        onSubmit={vi.fn()}
      />
    )

    expect(await screen.findAllByText("MiniMax-M3 (MiniMax-M3)")).toHaveLength(2)
    expect(screen.getByText("市场")).toBeVisible()
    expect(screen.getByText("基本面")).toBeVisible()
    expect(screen.getByText("新闻")).toBeVisible()
    expect(screen.getByText("社媒")).toBeVisible()
    expect(screen.getByRole("combobox", { name: "快速分析模型" })).toHaveClass("min-w-0")
    expect(screen.getByRole("combobox", { name: "深度决策模型" })).toHaveClass("min-w-0")
  })
})
