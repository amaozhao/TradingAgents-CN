"use client"

import { useMemo, useState } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Download, RefreshCw } from "lucide-react"
import { toast } from "sonner"

import { PageHeader } from "@/components/feedback/page-header"
import { TaskResultDialog } from "@/features/reports/task-result-dialog"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { analysisApi } from "@/libs/api/analysis"
import { formatDateTime } from "@/libs/utils/datetime"

type TaskTab = "running" | "completed" | "failed" | "all"

interface TaskRow {
  task_id?: string
  analysis_id?: string
  id?: string
  stock_code?: string
  stock_symbol?: string
  stock_name?: string
  market_type?: string
  status?: string
  progress?: number
  created_at?: string
  start_time?: string
  error_message?: string
  message?: string
}

type TaskPayload = { tasks?: TaskRow[]; items?: TaskRow[]; analyses?: TaskRow[]; total?: number } | TaskRow[]

function unwrapTasks(value: unknown): TaskPayload {
  if (value && typeof value === "object" && "data" in value) {
    const data = (value as { data: unknown }).data
    if (data && typeof data === "object" && "data" in data) return (data as { data: TaskPayload }).data
    return data as TaskPayload
  }
  return value as TaskPayload
}

const tabs: Array<{ value: TaskTab; label: string }> = [
  { value: "running", label: "进行中" },
  { value: "completed", label: "已完成" },
  { value: "failed", label: "失败" },
  { value: "all", label: "全部" }
]

export function TaskCenterPage() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const queryClient = useQueryClient()
  const initialTab = normalizeTab(searchParams.get("tab"))
  const initialTaskId = searchParams.get("task_id") || ""
  const [activeTab, setActiveTab] = useState<TaskTab>(initialTab)
  const [filters, setFilters] = useState({ startDate: "", endDate: "", market: "all", status: "all", stock: "" })
  const [keyword, setKeyword] = useState(initialTaskId)
  const [selectedIds, setSelectedIds] = useState<string[]>([])
  const [resultOpen, setResultOpen] = useState(false)
  const [currentResult, setCurrentResult] = useState<unknown>(null)

  const status = filters.status !== "all" ? filters.status : statusForTab(activeTab)
  const tasksQuery = useQuery({
    queryKey: ["tasks", activeTab, filters],
    queryFn: async () => {
      const historyPayload = unwrapTasks(await analysisApi.getHistory({
        status,
        market_type: filters.market === "all" ? undefined : filters.market,
        stock_code: filters.stock || undefined,
        start_date: filters.startDate || undefined,
        end_date: filters.endDate || undefined,
        page: 1,
        page_size: 100
      }))
      const historyRows = rowsFromPayload(historyPayload)
      if (historyRows.length || hasExtraFilters(filters)) return historyPayload
      return unwrapTasks(await analysisApi.getTaskList({ status, limit: 100, offset: 0 }))
    },
    refetchInterval: activeTab === "running" ? 5_000 : false,
    retry: false
  })

  const rows = rowsFromPayload(tasksQuery.data)
  const filteredRows = useMemo(() => {
    const text = keyword.trim().toLowerCase()
    if (!text) return rows
    return rows.filter((row) => `${taskId(row)} ${row.stock_code || row.stock_symbol || ""} ${row.stock_name || ""}`.toLowerCase().includes(text))
  }, [keyword, rows])
  const selectedSet = useMemo(() => new Set(selectedIds), [selectedIds])
  const stats = useMemo(() => {
    const completed = rows.filter((row) => row.status === "completed").length
    const failed = rows.filter((row) => row.status === "failed").length
    const uniqueStocks = new Set(rows.map((row) => row.stock_code || row.stock_symbol).filter(Boolean)).size
    return { total: rows.length, completed, failed, uniqueStocks }
  }, [rows])

  const deleteMutation = useMutation({
    mutationFn: (id: string) => analysisApi.deleteTask(id),
    onSuccess: () => {
      toast.success("任务已删除")
      void queryClient.invalidateQueries({ queryKey: ["tasks"] })
    },
    onError: (error) => toast.error(error.message)
  })
  const failMutation = useMutation({
    mutationFn: (id: string) => analysisApi.markTaskAsFailed(id),
    onSuccess: () => {
      toast.success("任务已标记为失败")
      void queryClient.invalidateQueries({ queryKey: ["tasks"] })
    },
    onError: (error) => toast.error(error.message)
  })

  const openResult = async (row: TaskRow) => {
    const id = taskId(row)
    if (!id) return
    try {
      const result = await analysisApi.getTaskResult(id)
      setCurrentResult(result)
      setResultOpen(true)
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "获取结果失败")
    }
  }

  const exportSelected = () => {
    const selected = rows.filter((row) => selectedSet.has(taskId(row)))
    if (!selected.length) return
    const blob = new Blob([JSON.stringify(selected, null, 2)], { type: "application/json;charset=utf-8" })
    const url = URL.createObjectURL(blob)
    const link = document.createElement("a")
    link.href = url
    link.download = `tasks_selected_${Date.now()}.json`
    link.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div>
      <PageHeader
        title="任务中心"
        description="统一查看并管理分析任务：进行中 / 已完成 / 失败"
        actions={<Button onClick={() => router.push("/analysis/single")}>新建分析</Button>}
      />
      <Card>
        <CardContent className="p-6">
          <Tabs
            value={activeTab}
            onValueChange={(value) => {
              const tab = normalizeTab(value)
              setActiveTab(tab)
              router.replace(tab === "running" ? "/tasks" : `/tasks?tab=${tab}`)
            }}
          >
            <TabsList className="flex h-auto flex-wrap justify-start">
              {tabs.map((tab) => <TabsTrigger key={tab.value} value={tab.value}>{tab.label}</TabsTrigger>)}
            </TabsList>
            {tabs.map((tab) => <TabsContent key={tab.value} value={tab.value} className="mt-4" />)}
          </Tabs>
        </CardContent>
      </Card>

      <Card className="mt-4">
        <CardContent className="grid gap-4 p-6 md:grid-cols-5">
          <div className="grid gap-2"><Label>开始日期</Label><Input type="date" value={filters.startDate} onChange={(event) => setFilters((value) => ({ ...value, startDate: event.target.value }))} /></div>
          <div className="grid gap-2"><Label>结束日期</Label><Input type="date" value={filters.endDate} onChange={(event) => setFilters((value) => ({ ...value, endDate: event.target.value }))} /></div>
          <div className="grid gap-2">
            <Label>市场</Label>
            <Select value={filters.market} onValueChange={(market) => setFilters((value) => ({ ...value, market }))}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="all">全部</SelectItem>
                <SelectItem value="A股">A股</SelectItem>
                <SelectItem value="港股">港股</SelectItem>
                <SelectItem value="美股">美股</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="grid gap-2">
            <Label>状态</Label>
            <Select value={filters.status} onValueChange={(statusValue) => setFilters((value) => ({ ...value, status: statusValue }))}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="all">全部</SelectItem>
                <SelectItem value="processing">进行中</SelectItem>
                <SelectItem value="completed">已完成</SelectItem>
                <SelectItem value="failed">失败</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="grid gap-2"><Label>股票</Label><Input placeholder="代码或名称" value={filters.stock} onChange={(event) => setFilters((value) => ({ ...value, stock: event.target.value }))} /></div>
          <div className="flex gap-2 md:col-span-5">
            <Button onClick={() => void tasksQuery.refetch()} disabled={tasksQuery.isFetching}>查询</Button>
            <Button variant="outline" onClick={() => setFilters({ startDate: "", endDate: "", market: "all", status: "all", stock: "" })}>重置</Button>
          </div>
        </CardContent>
      </Card>

      <div className="mt-4 grid gap-4 md:grid-cols-4">
        <Stat label="总任务" value={stats.total} />
        <Stat label="已完成" value={stats.completed} />
        <Stat label="失败" value={stats.failed} />
        <Stat label="股票数" value={stats.uniqueStocks} />
      </div>

      <Card className="mt-6">
        <CardContent className="p-6">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <div className="flex flex-wrap gap-2">
              <Input className="w-56" placeholder="搜索股票代码/名称" value={keyword} onChange={(event) => setKeyword(event.target.value)} />
              <Button variant="outline" onClick={() => void tasksQuery.refetch()} disabled={tasksQuery.isFetching}>
                <RefreshCw className="mr-2 size-4" />
                刷新
              </Button>
            </div>
            <Button variant="outline" onClick={exportSelected} disabled={!selectedIds.length}>
              <Download className="mr-2 size-4" />
              导出所选
            </Button>
          </div>
          <div className="overflow-x-auto rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-10"><span className="sr-only">选择</span></TableHead>
                  <TableHead>任务ID</TableHead>
                  <TableHead>股票代码</TableHead>
                  <TableHead>股票名称</TableHead>
                  <TableHead>状态</TableHead>
                  <TableHead>进度</TableHead>
                  <TableHead>开始时间</TableHead>
                  <TableHead>操作</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredRows.length ? filteredRows.map((row) => {
                  const id = taskId(row)
                  return (
                    <TableRow key={id || `${row.stock_code}-${row.created_at}`}>
                      <TableCell><input aria-label={`选择 ${id}`} type="checkbox" checked={selectedSet.has(id)} onChange={(event) => setSelectedIds((current) => event.target.checked ? [...current, id] : current.filter((item) => item !== id))} /></TableCell>
                      <TableCell className="max-w-48 truncate">{id || "-"}</TableCell>
                      <TableCell>{row.stock_code || row.stock_symbol || "-"}</TableCell>
                      <TableCell>{row.stock_name || "-"}</TableCell>
                      <TableCell><Badge variant={row.status === "failed" ? "destructive" : row.status === "completed" ? "default" : "secondary"}>{formatStatus(row.status)}</Badge></TableCell>
                      <TableCell>{Number(row.progress || 0)}%</TableCell>
                      <TableCell>{formatDateTime(row.start_time || row.created_at || "")}</TableCell>
                      <TableCell>
                        <div className="flex flex-wrap gap-2">
                          {row.status === "completed" ? <Button size="sm" variant="outline" onClick={() => void openResult(row)}>查看结果</Button> : null}
                          {row.status === "completed" ? <Button size="sm" variant="outline" onClick={() => router.push(`/reports/view/${id}`)}>报告详情</Button> : null}
                          {row.status === "failed" ? <Button size="sm" variant="outline" onClick={() => toast.error(row.error_message || row.message || "未知错误")}>查看错误</Button> : null}
                          {isRunning(row.status) ? <Button size="sm" variant="outline" onClick={() => id && failMutation.mutate(id)}>标记失败</Button> : null}
                          <Button size="sm" variant="outline" onClick={() => id && deleteMutation.mutate(id)}>删除</Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  )
                }) : (
                  <TableRow><TableCell colSpan={8} className="h-24 text-center text-muted-foreground">暂无任务</TableCell></TableRow>
                )}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>
      <TaskResultDialog open={resultOpen} result={currentResult} onOpenChange={setResultOpen} />
    </div>
  )
}

function rowsFromPayload(payload?: TaskPayload) {
  if (!payload) return []
  return Array.isArray(payload) ? payload : payload.tasks || payload.items || payload.analyses || []
}

function hasExtraFilters(filters: { startDate: string; endDate: string; market: string; status: string; stock: string }) {
  return Boolean(filters.startDate || filters.endDate || filters.stock || filters.market !== "all" || filters.status !== "all")
}

function normalizeTab(value?: string | null): TaskTab {
  return value === "completed" || value === "failed" || value === "all" ? value : "running"
}

function statusForTab(tab: TaskTab) {
  if (tab === "all") return undefined
  if (tab === "running") return "processing"
  return tab
}

function taskId(row: TaskRow) {
  return row.task_id || row.analysis_id || row.id || ""
}

function isRunning(status?: string) {
  return status === "pending" || status === "processing" || status === "running"
}

function formatStatus(status?: string) {
  const map: Record<string, string> = {
    pending: "等待中",
    processing: "处理中",
    running: "运行中",
    completed: "已完成",
    failed: "失败",
    cancelled: "已取消"
  }
  return status ? map[status] ?? status : "-"
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <Card>
      <CardContent className="p-5">
        <div className="text-sm text-muted-foreground">{label}</div>
        <div className="mt-2 text-2xl font-semibold">{value}</div>
      </CardContent>
    </Card>
  )
}
