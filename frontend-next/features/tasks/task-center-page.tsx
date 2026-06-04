"use client"

import { useRouter, useSearchParams } from "next/navigation"
import { useQuery } from "@tanstack/react-query"
import type { ColumnDef } from "@tanstack/react-table"

import { DataTable } from "@/components/data-table/data-table"
import { PageHeader } from "@/components/feedback/page-header"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { analysisApi } from "@/libs/api/analysis"
import { formatDateTime } from "@/libs/utils/datetime"

interface TaskRow {
  task_id?: string
  id?: string
  stock_code?: string
  stock_name?: string
  status?: string
  progress?: number
  priority?: string
  created_at?: string
}

type TaskPayload = { tasks?: TaskRow[]; items?: TaskRow[]; total?: number } | TaskRow[]

function unwrapTasks(value: unknown): TaskPayload {
  if (value && typeof value === "object" && "data" in value) {
    return (value as { data: TaskPayload }).data
  }
  return value as TaskPayload
}

const columns: ColumnDef<TaskRow>[] = [
  {
    accessorKey: "task_id",
    header: "任务ID",
    cell: ({ row }) => row.original.task_id || row.original.id || "-"
  },
  {
    accessorKey: "stock_code",
    header: "股票代码",
    cell: ({ row }) => row.original.stock_code || "-"
  },
  {
    accessorKey: "status",
    header: "状态",
    cell: ({ row }) => <Badge variant={row.original.status === "completed" ? "default" : "secondary"}>{formatStatus(row.original.status)}</Badge>
  },
  {
    accessorKey: "progress",
    header: "进度",
    cell: ({ row }) => `${Number(row.original.progress || 0)}%`
  },
  {
    accessorKey: "created_at",
    header: "创建时间",
    cell: ({ row }) => formatDateTime(row.original.created_at || "")
  }
]

export function TaskCenterPage() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const activeTab = searchParams.get("tab") === "completed" ? "completed" : "active"
  const status = activeTab === "completed" ? "completed" : undefined

  const tasksQuery = useQuery({
    queryKey: ["tasks", activeTab],
    queryFn: async () => unwrapTasks(await analysisApi.getTaskList({ status, limit: 50, offset: 0 })),
    refetchInterval: activeTab === "active" ? 10_000 : false,
    retry: false
  })

  const payload = tasksQuery.data
  const rows = Array.isArray(payload) ? payload : payload?.tasks || payload?.items || []

  return (
    <div>
      <PageHeader
        title="任务中心"
        description="查看进行中和已完成的分析任务，跟踪进度并进入报告结果。"
        actions={
          <Button onClick={() => router.push("/analysis/single")}>
            新建分析
          </Button>
        }
      />
      <Card>
        <CardContent className="p-6">
          <Tabs
            value={activeTab}
            onValueChange={(value) => {
              router.replace(value === "completed" ? "/tasks?tab=completed" : "/tasks")
            }}
          >
            <TabsList>
              <TabsTrigger value="active">进行中</TabsTrigger>
              <TabsTrigger value="completed">已完成</TabsTrigger>
            </TabsList>
            <TabsContent value="active" className="mt-4">
              <DataTable columns={columns} data={rows} loading={tasksQuery.isLoading} emptyText="暂无进行中的任务" />
            </TabsContent>
            <TabsContent value="completed" className="mt-4">
              <DataTable columns={columns} data={rows} loading={tasksQuery.isLoading} emptyText="暂无已完成任务" />
            </TabsContent>
          </Tabs>
        </CardContent>
      </Card>
    </div>
  )
}

function formatStatus(status?: string) {
  const map: Record<string, string> = {
    pending: "等待中",
    running: "运行中",
    completed: "已完成",
    failed: "失败"
  }
  return status ? map[status] ?? status : "-"
}
