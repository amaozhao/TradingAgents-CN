"use client"

import Link from "next/link"
import { useMemo, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import type { ColumnDef } from "@tanstack/react-table"

import { DataTable } from "@/components/data-table/data-table"
import { PageHeader } from "@/components/feedback/page-header"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { fetchReports, type ReportListItem } from "@/features/reports/report-api"
import { formatDateTime } from "@/libs/utils/datetime"

export function ReportsPage() {
  const [keyword, setKeyword] = useState("")
  const [market, setMarket] = useState("")
  const params = useMemo(() => {
    const next = new URLSearchParams({ page: "1", page_size: "20" })
    if (keyword) next.set("keyword", keyword)
    if (market) next.set("market", market)
    return next
  }, [keyword, market])

  const reportsQuery = useQuery({
    queryKey: ["reports", params.toString()],
    queryFn: () => fetchReports(params),
    retry: false
  })

  const columns: ColumnDef<ReportListItem>[] = [
    {
      accessorKey: "title",
      header: "报告标题",
      cell: ({ row }) => (
        <Link href={`/reports/view/${row.original.id}`} className="font-medium text-primary hover:underline">
          {row.original.title}
        </Link>
      )
    },
    {
      accessorKey: "stock_code",
      header: "股票",
      cell: ({ row }) => `${row.original.stock_code || "-"} ${row.original.stock_name || ""}`
    },
    {
      accessorKey: "type",
      header: "类型",
      cell: ({ row }) => <Badge variant="secondary">{formatType(row.original.type)}</Badge>
    },
    {
      accessorKey: "status",
      header: "状态",
      cell: ({ row }) => <Badge>{formatStatus(row.original.status)}</Badge>
    },
    {
      accessorKey: "created_at",
      header: "创建时间",
      cell: ({ row }) => formatDateTime(row.original.created_at || "")
    }
  ]

  return (
    <div>
      <PageHeader
        title="分析报告"
        description="查看和管理股票分析报告，支持多种格式导出。"
        actions={
          <Button asChild variant="outline">
            <Link href="/reports/token">Token统计</Link>
          </Button>
        }
      />
      <Card className="mb-6">
        <CardContent className="flex flex-col gap-3 p-4 md:flex-row">
          <Input value={keyword} onChange={(event) => setKeyword(event.target.value)} placeholder="搜索股票代码或名称" className="max-w-sm" />
          <select
            value={market}
            onChange={(event) => setMarket(event.target.value)}
            className="h-9 rounded-md border bg-background px-3 text-sm"
            aria-label="市场筛选"
          >
            <option value="">全部市场</option>
            <option value="A股">A股</option>
            <option value="港股">港股</option>
            <option value="美股">美股</option>
          </select>
          <Button variant="outline" onClick={() => reportsQuery.refetch()}>
            刷新
          </Button>
        </CardContent>
      </Card>
      <DataTable
        columns={columns}
        data={reportsQuery.data?.reports || []}
        loading={reportsQuery.isLoading}
        emptyText="暂无分析报告"
        enableRowSelection
      />
    </div>
  )
}

function formatType(type?: string) {
  const map: Record<string, string> = { analysis: "分析报告", summary: "摘要报告" }
  return type ? map[type] ?? type : "-"
}

function formatStatus(status?: string) {
  const map: Record<string, string> = { completed: "已完成", generating: "生成中", failed: "失败" }
  return status ? map[status] ?? status : "-"
}
