import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

import { TaskCenterPage } from "@/features/tasks/task-center-page"

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  useSearchParams: () => new URLSearchParams("")
}))

vi.mock("@/libs/api/analysis", () => ({
  analysisApi: {
    getHistory: vi.fn(async () => ({ data: { tasks: [], total: 0 } })),
    getTaskList: vi.fn(async () => ({ data: { tasks: [], total: 0 } })),
    getTaskResult: vi.fn(),
    deleteTask: vi.fn(),
    markTaskAsFailed: vi.fn()
  }
}))

function renderWithQueryClient(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false }
    }
  })

  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>)
}

describe("TaskCenterPage", () => {
  it("keeps the Vue task tabs and management filters", () => {
    renderWithQueryClient(<TaskCenterPage />)

    expect(screen.getByRole("tab", { name: "进行中" })).toBeInTheDocument()
    expect(screen.getByRole("tab", { name: "已完成" })).toBeInTheDocument()
    expect(screen.getByRole("tab", { name: "失败" })).toBeInTheDocument()
    expect(screen.getByRole("tab", { name: "全部" })).toBeInTheDocument()
    expect(screen.getByText("开始日期")).toBeInTheDocument()
    expect(screen.getByText("市场")).toBeInTheDocument()
    expect(screen.getAllByText("状态").length).toBeGreaterThan(0)
    expect(screen.getByText("股票")).toBeInTheDocument()
    expect(screen.getByText("总任务")).toBeInTheDocument()
    expect(screen.getByText("导出所选")).toBeInTheDocument()
  })
})
