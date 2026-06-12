import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
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

  it("prefills symbols passed from the Agent route", async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn()
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
        initialSymbols="000001,600519"
        running={false}
        onCancel={vi.fn()}
        onSave={vi.fn()}
        onSubmit={onSubmit}
      />
    )

    expect(screen.getByLabelText("股票代码列表")).toHaveValue("000001\n600519")
    await screen.findAllByText("MiniMax-M3 (MiniMax-M3)")
    await user.type(screen.getByLabelText("批次标题"), "银行批量分析")
    await user.click(screen.getByRole("button", { name: "开始批量分析" }))

    expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({
      payload: expect.objectContaining({
        symbols: ["000001", "600519"],
        stock_codes: ["000001", "600519"]
      })
    }))
  })
})
