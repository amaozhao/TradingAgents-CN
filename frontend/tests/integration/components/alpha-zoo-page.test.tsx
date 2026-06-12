import type { ReactNode } from "react"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { AlphaBenchPage } from "@/features/alpha-zoo/alpha-bench-page"
import { AlphaFactorDetailPage } from "@/features/alpha-zoo/alpha-factor-detail-page"
import { AlphaFactorTable } from "@/features/alpha-zoo/alpha-factor-table"
import { AlphaZooPage } from "@/features/alpha-zoo/alpha-zoo-page"
import { alphaZooApi } from "@/libs/api/alpha-zoo"

const navigationMock = vi.hoisted(() => ({
  searchParams: new URLSearchParams()
}))

vi.mock("next/link", () => ({
  default: ({ children, href, className }: { children: ReactNode; href: string; className?: string }) => (
    <a href={href} className={className}>{children}</a>
  )
}))

vi.mock("next/navigation", () => ({
  useSearchParams: () => navigationMock.searchParams
}))

vi.mock("@/libs/api/alpha-zoo", () => ({
  alphaZooApi: {
    list: vi.fn(),
    detail: vi.fn(),
    bench: vi.fn(),
    compare: vi.fn()
  }
}))

const sampleFactor = {
  factor_id: "alpha101_001",
  id: "alpha101_001",
  family: "alpha101",
  zoo: "alpha101",
  number: 1,
  name: "Kakushadze Alpha #1",
  nickname: "Kakushadze Alpha #1",
  description: "Kakushadze Alpha #1",
  required_columns: ["close", "returns"],
  columns_required: ["close", "returns"],
  theme: ["reversal", "volatility"],
  formula_latex: "rank(ts_argmax(SignedPower((returns<0)?stddev(returns,20):close, 2.), 5)) - 0.5",
  extras_required: [],
  requires_sector: false,
  universe: ["equity_us"],
  frequency: ["1D"],
  decay_horizon: 5,
  min_warmup_bars: 25,
  notes: "",
  module_path: "trader.factors.zoo.alpha101.alpha_001",
  meta: {}
}

describe("AlphaZooPage", () => {
  beforeEach(() => {
    Element.prototype.hasPointerCapture ??= () => false
    Element.prototype.scrollIntoView ??= () => undefined
    vi.mocked(alphaZooApi.list).mockResolvedValue({
      success: true,
      data: { items: [sampleFactor], alphas: [sampleFactor], total: 1, returned: 1, truncated: false },
      message: "ok"
    })
    vi.mocked(alphaZooApi.detail).mockReset()
    vi.mocked(alphaZooApi.bench).mockReset()
    vi.mocked(alphaZooApi.compare).mockReset()
    navigationMock.searchParams = new URLSearchParams()
  })

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

  it("links catalogue factor ids to detail routes", () => {
    render(
      <AlphaFactorTable
        factors={[sampleFactor]}
        selectedIds={new Set()}
      />
    )

    expect(screen.getByRole("link", { name: "alpha101_001" })).toHaveAttribute(
      "href",
      "/alpha-zoo/alpha101_001"
    )
  })

  it("renders alpha detail summary without duplicating formula content", async () => {
    const formula = "rank(ts_argmax(SignedPower((returns<0)?stddev(returns,20):close, 2.), 5)) - 0.5"

    vi.mocked(alphaZooApi.detail).mockResolvedValue({
      success: true,
      data: {
        ...sampleFactor,
        description: formula,
        alpha: {
          id: "alpha101_001",
          zoo: "alpha101",
          module_path: "trader.factors.zoo.alpha101.alpha_001",
          meta: {}
        },
        source_code: "class Alpha001: pass\n"
      },
      message: "ok"
    })

    const { container } = render(<AlphaFactorDetailPage alphaId="alpha101_001" />)

    expect(await screen.findByRole("heading", { name: "alpha101_001" })).toBeInTheDocument()
    expect(alphaZooApi.detail).toHaveBeenCalledWith("alpha101_001")
    expect(screen.getByText("Kakushadze Alpha #1")).toBeInTheDocument()
    expect(screen.getByTestId("alpha-detail-summary")).not.toHaveTextContent(formula)
    expect(screen.getByTestId("alpha-detail-formula")).toHaveAttribute("aria-label", formula)
    expect(screen.getByText("trader.factors.zoo.alpha101.alpha_001")).toBeInTheDocument()
    expect(container.querySelector("details")).not.toHaveAttribute("open")
    expect(screen.getByText("查看源码 (1 行)")).toBeInTheDocument()
    expect(screen.getByRole("link", { name: "返回 Alpha 因子库" })).toHaveAttribute("href", "/alpha-zoo")
    expect(screen.getByRole("link", { name: "运行该因子测试" })).toHaveAttribute("href", "/alpha-zoo/bench?alpha_id=alpha101_001&zoo=alpha101")
  })

  it("runs a single-factor coverage check when alpha_id is provided", async () => {
    navigationMock.searchParams = new URLSearchParams("alpha_id=alpha101_001&zoo=alpha101")
    vi.mocked(alphaZooApi.bench).mockResolvedValue({
      success: true,
      data: {
        job_id: "job-single",
        status: "completed",
        result: {
          kind: "alpha_bench",
          alpha_id: "alpha101_001",
          summary: {
            factor_id: "alpha101_001",
            rows: 360,
            columns: 3,
            non_null_values: 324
          },
          classification: "alive"
        }
      },
      message: "ok"
    })

    render(<AlphaBenchPage />)
    expect(await screen.findByRole("checkbox", { name: /alpha101_001/ })).toBeChecked()
    expect(screen.queryByLabelText("目标因子")).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole("button", { name: "运行覆盖检查" }))

    expect(alphaZooApi.bench).toHaveBeenCalledWith({
      alpha_id: "alpha101_001",
      symbols: ["600519", "000001", "300750"],
      start_date: "2025-01-01",
      end_date: "2026-06-03"
    })
    expect(alphaZooApi.compare).not.toHaveBeenCalled()
    expect(await screen.findAllByText("30.0%")).toHaveLength(2)
    expect(screen.getByText("有效日期数")).toBeInTheDocument()
    expect(screen.getByText("股票数量")).toBeInTheDocument()
    expect(screen.getByText("有效因子值")).toBeInTheDocument()
    expect(screen.getAllByText("覆盖率").length).toBeGreaterThan(0)
    expect(screen.getByText(/当前是因子输出覆盖检查/)).toBeInTheDocument()
  })

  it("runs a batch coverage check when the target factor is cleared", async () => {
    navigationMock.searchParams = new URLSearchParams("zoo=alpha101")
    vi.mocked(alphaZooApi.compare).mockResolvedValue({
      success: true,
      data: {
        job_id: "job-batch",
        status: "completed",
        result: {
          kind: "alpha_compare",
          alpha_ids: ["alpha101_001"],
          symbols: ["600519", "000001", "300750"],
          rows: [
            {
              factor_id: "alpha101_001",
              rows: 360,
              columns: 3,
              non_null_values: 1080
            }
          ]
        }
      },
      message: "ok"
    })

    render(<AlphaBenchPage />)
    expect(await screen.findByRole("checkbox", { name: /alpha101_001/ })).not.toBeChecked()
    await userEvent.click(screen.getByRole("button", { name: "运行覆盖检查" }))

    expect(alphaZooApi.compare).toHaveBeenCalledWith({
      alpha_ids: ["alpha101_001"],
      symbols: ["600519", "000001", "300750"],
      start_date: "2025-01-01",
      end_date: "2026-06-03"
    })
    expect(alphaZooApi.bench).not.toHaveBeenCalled()
  })

  it("runs selected factors as a multi-factor coverage check", async () => {
    const secondFactor = { ...sampleFactor, id: "alpha101_002", factor_id: "alpha101_002", number: 2 }
    vi.mocked(alphaZooApi.list).mockResolvedValue({
      success: true,
      data: { items: [sampleFactor, secondFactor], alphas: [sampleFactor, secondFactor], total: 2, returned: 2, truncated: false },
      message: "ok"
    })
    vi.mocked(alphaZooApi.compare).mockResolvedValue({
      success: true,
      data: {
        job_id: "job-selected",
        status: "completed",
        result: {
          kind: "alpha_compare",
          alpha_ids: ["alpha101_001", "alpha101_002"],
          rows: []
        }
      },
      message: "ok"
    })

    render(<AlphaBenchPage />)
    await userEvent.click(await screen.findByRole("checkbox", { name: /alpha101_001/ }))
    await userEvent.click(screen.getByRole("checkbox", { name: /alpha101_002/ }))
    await userEvent.click(screen.getByRole("button", { name: "运行覆盖检查" }))

    expect(alphaZooApi.compare).toHaveBeenCalledWith({
      alpha_ids: ["alpha101_001", "alpha101_002"],
      symbols: ["600519", "000001", "300750"],
      start_date: "2025-01-01",
      end_date: "2026-06-03"
    })
    expect(alphaZooApi.bench).not.toHaveBeenCalled()
  })

  it("keeps a manual zoo change instead of resetting to URL params", async () => {
    const academicFactor = {
      ...sampleFactor,
      id: "academic_carhart_mom",
      factor_id: "academic_carhart_mom",
      family: "academic",
      zoo: "academic",
      name: "Carhart Momentum",
      nickname: "Carhart 1997 momentum"
    }
    navigationMock.searchParams = new URLSearchParams("alpha_id=academic_carhart_mom&zoo=academic")
    vi.mocked(alphaZooApi.list).mockImplementation(async (params) => ({
      success: true,
      data: {
        items: params?.zoo === "academic" ? [academicFactor] : [sampleFactor],
        alphas: params?.zoo === "academic" ? [academicFactor] : [sampleFactor],
        total: 1,
        returned: 1,
        truncated: false
      },
      message: "ok"
    }))

    render(<AlphaBenchPage />)
    expect(await screen.findByRole("checkbox", { name: /academic_carhart_mom/ })).toBeChecked()

    await userEvent.click(screen.getByRole("combobox"))
    await userEvent.click(await screen.findByRole("option", { name: "Kakushadze 101" }))

    expect(await screen.findByRole("checkbox", { name: /alpha101_001/ })).not.toBeChecked()
    expect(screen.queryByRole("checkbox", { name: /academic_carhart_mom/ })).not.toBeInTheDocument()
  })

  it("shows animated running feedback while a coverage check is pending", async () => {
    navigationMock.searchParams = new URLSearchParams("alpha_id=alpha101_001&zoo=alpha101")
    let resolveJob: (value: Awaited<ReturnType<typeof alphaZooApi.bench>>) => void = () => undefined
    vi.mocked(alphaZooApi.bench).mockReturnValue(
      new Promise((resolve) => {
        resolveJob = resolve
      })
    )

    render(<AlphaBenchPage />)
    expect(await screen.findByRole("checkbox", { name: /alpha101_001/ })).toBeChecked()
    await userEvent.click(screen.getByRole("button", { name: "运行覆盖检查" }))

    expect(screen.getByRole("button", { name: "运行中" })).toHaveClass("animate-pulse")
    expect(screen.getAllByTestId("alpha-bench-loading-row")).toHaveLength(3)

    resolveJob({
      success: true,
      data: {
        job_id: "job-single",
        status: "completed",
        result: {
          kind: "alpha_bench",
          alpha_id: "alpha101_001",
          summary: {
            factor_id: "alpha101_001",
            rows: 360,
            columns: 3,
            non_null_values: 324
          },
          classification: "alive"
        }
      },
      message: "ok"
    })

    expect(await screen.findAllByText("30.0%")).toHaveLength(2)
  })
})
