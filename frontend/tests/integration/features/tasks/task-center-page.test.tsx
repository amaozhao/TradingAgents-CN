import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { TaskCenterPage } from "@/features/tasks/task-center-page"
import { analysisApi } from "@/libs/api/analysis"

let search = ""
const routerPush = vi.fn()
const routerReplace = vi.fn()
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: routerPush, replace: routerReplace }),
  useSearchParams: () => new URLSearchParams(search)
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
  beforeEach(() => {
    vi.clearAllMocks()
    search = ""
    vi.mocked(analysisApi.getHistory).mockResolvedValue({ data: { tasks: [], total: 0 } })
    vi.mocked(analysisApi.getTaskList).mockResolvedValue({ data: { tasks: [], total: 0 } })
  })

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

  it("uses Agent task_id links to focus the matching task row", async () => {
    search = "task_id=task-600519"
    vi.mocked(analysisApi.getTaskList).mockResolvedValue({
      data: {
        tasks: [
          {
            task_id: "task-600519",
            stock_code: "600519",
            stock_name: "贵州茅台",
            status: "processing",
            progress: 45,
            start_time: "2026-06-11T10:00:00Z"
          },
          {
            task_id: "task-000001",
            stock_code: "000001",
            stock_name: "平安银行",
            status: "processing",
            progress: 10,
            start_time: "2026-06-11T10:05:00Z"
          }
        ],
        total: 2
      }
    })

    renderWithQueryClient(<TaskCenterPage />)

    expect(screen.getByPlaceholderText("搜索股票代码/名称")).toHaveValue("task-600519")
    await waitFor(() => expect(screen.getByText("task-600519")).toBeInTheDocument())
    expect(screen.getByText("贵州茅台")).toBeInTheDocument()
    expect(screen.queryByText("task-000001")).not.toBeInTheDocument()
  })

  it("passes batch_id from the URL and renders child task rows", async () => {
    search = "batch_id=batch-1"
    vi.mocked(analysisApi.getHistory).mockResolvedValue({
      data: {
        tasks: [
          {
            task_id: "task-1",
            batch_id: "batch-1",
            stock_code: "600036",
            stock_name: "招商银行",
            status: "completed",
            progress: 100,
            start_time: "2026-06-12T10:00:00Z"
          },
          {
            task_id: "task-2",
            batch_id: "batch-1",
            stock_code: "000001",
            stock_name: "平安银行",
            status: "processing",
            progress: 40,
            start_time: "2026-06-12T10:01:00Z"
          }
        ],
        total: 2
      }
    })

    renderWithQueryClient(<TaskCenterPage />)

    await waitFor(() => {
      expect(analysisApi.getHistory).toHaveBeenCalledWith(
        expect.objectContaining({ batch_id: "batch-1" })
      )
    })
    expect(await screen.findByText("task-1")).toBeInTheDocument()
    expect(screen.getByText("招商银行")).toBeInTheDocument()
    expect(screen.getByText("100%")).toBeInTheDocument()
    expect(screen.getByText("task-2")).toBeInTheDocument()
    expect(screen.getByText("40%")).toBeInTheDocument()
    expect(analysisApi.getTaskList).not.toHaveBeenCalled()
  })

  it("keeps batch_id in the URL when switching task tabs", async () => {
    search = "batch_id=batch-1"

    renderWithQueryClient(<TaskCenterPage />)

    await userEvent.click(screen.getByRole("tab", { name: "已完成" }))

    await waitFor(() => {
      expect(routerReplace).toHaveBeenCalledWith(
        "/tasks?tab=completed&batch_id=batch-1"
      )
    })
  })
})
