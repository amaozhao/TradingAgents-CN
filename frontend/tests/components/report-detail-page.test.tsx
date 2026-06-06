import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi } from "vitest"

import { ReportDetailPage } from "@/features/reports/report-detail-page"
import { downloadReport, fetchReportDetail } from "@/features/reports/report-api"

const push = vi.fn()

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push })
}))

vi.mock("next/link", () => ({
  default: ({ children, href }: { children: React.ReactNode; href: string }) => (
    <a href={href}>{children}</a>
  )
}))

vi.mock("@/features/learning/markdown-renderer", () => ({
  MarkdownRenderer: ({ content }: { content: string }) => <div>{content}</div>
}))

vi.mock("@/features/reports/report-api", () => ({
  fetchReportDetail: vi.fn(),
  downloadReport: vi.fn()
}))

function renderWithQueryClient(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false }
    }
  })

  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>)
}

describe("ReportDetailPage", () => {
  it("renders report sections with readable groups and hides duplicate raw agent keys", async () => {
    vi.mocked(fetchReportDetail).mockResolvedValue({
      id: "7fbec504cc0d414f98fa6421",
      stock_symbol: "600519",
      stock_name: "贵州茅台",
      status: "completed",
      recommendation: "买入",
      risk_level: "中等",
      confidence_score: 0.72,
      summary: "摘要内容",
      created_at: "2026-06-06T18:37:24+08:00",
      reports: {
        safe_analyst: "保守观点",
        risky_analyst: "激进观点",
        bear_researcher: "看跌观点",
        bull_researcher: "看涨观点",
        investment_plan: "研究团队计划重复内容",
        research_team_decision: "研究团队计划重复内容",
        trader_investment_plan: "交易计划",
        risk_management_decision: "最终裁决重复内容",
        final_trade_decision: "最终裁决重复内容",
        market_report: "市场报告",
        fundamentals_report: "基本面报告"
      }
    })

    renderWithQueryClient(<ReportDetailPage id="7fbec504cc0d414f98fa6421" />)

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "总览" })).toBeInTheDocument()
    })

    expect(screen.getByRole("heading", { name: "核心报告" })).toBeInTheDocument()
    expect(screen.getByRole("heading", { name: "多方辩论" })).toBeInTheDocument()
    expect(screen.getByRole("heading", { name: "风险评审" })).toBeInTheDocument()
    expect(screen.getByRole("heading", { name: "决策链路" })).toBeInTheDocument()

    expect(screen.getByRole("heading", { name: "保守风险分析师" })).toBeInTheDocument()
    expect(screen.getByRole("heading", { name: "激进风险分析师" })).toBeInTheDocument()
    expect(screen.getByRole("heading", { name: "看跌研究员" })).toBeInTheDocument()
    expect(screen.getByRole("heading", { name: "看涨研究员" })).toBeInTheDocument()
    expect(screen.getByRole("heading", { name: "最终交易决策" })).toBeInTheDocument()

    expect(screen.queryByRole("heading", { name: "safe_analyst" })).not.toBeInTheDocument()
    expect(screen.queryByRole("heading", { name: "risk_management_decision" })).not.toBeInTheDocument()
    expect(screen.queryByRole("heading", { name: "investment_plan" })).not.toBeInTheDocument()

    expect(screen.getAllByText("研究团队计划重复内容")).toHaveLength(1)
    expect(screen.getAllByText("最终裁决重复内容")).toHaveLength(1)
  })

  it("downloads the report and applies buy recommendations to paper trading", async () => {
    const user = userEvent.setup()
    vi.mocked(fetchReportDetail).mockResolvedValue({
      id: "report-1",
      stock_symbol: "600519",
      stock_name: "贵州茅台",
      status: "completed",
      recommendation: "买入",
      risk_level: "中等",
      confidence_score: 80,
      summary: "建议买入",
      created_at: "2026-06-06T18:37:24+08:00",
      reports: {}
    })
    vi.mocked(downloadReport).mockResolvedValue(undefined)

    renderWithQueryClient(<ReportDetailPage id="report-1" />)

    await user.click(await screen.findByRole("button", { name: "下载报告" }))
    await waitFor(() => expect(downloadReport).toHaveBeenCalledWith("report-1", "markdown", expect.stringContaining("600519")))

    await user.click(screen.getByRole("button", { name: "应用到交易" }))
    expect(push).toHaveBeenCalledWith("/paper?code=600519&side=buy&quantity=100&analysis_id=report-1")
  })
})
