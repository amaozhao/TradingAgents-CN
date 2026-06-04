"use client"

import { useQuery } from "@tanstack/react-query"
import type { ColumnDef } from "@tanstack/react-table"

import { DataTable } from "@/components/data-table/data-table"
import { EChartPanel } from "@/components/charts/e-chart-panel"
import { PageHeader } from "@/components/feedback/page-header"
import { Card, CardContent } from "@/components/ui/card"
import { getUsageRecords, getUsageStatistics, type UsageRecord } from "@/libs/api/usage"

function unwrap<T>(value: T | { data: T }): T {
  return value && typeof value === "object" && "data" in value ? (value as { data: T }).data : (value as T)
}

const columns: ColumnDef<UsageRecord>[] = [
  { accessorKey: "provider", header: "供应商" },
  { accessorKey: "model_name", header: "模型" },
  { accessorKey: "input_tokens", header: "输入Token" },
  { accessorKey: "output_tokens", header: "输出Token" },
  {
    id: "total_tokens",
    header: "总Token",
    cell: ({ row }) => row.original.input_tokens + row.original.output_tokens
  },
  { accessorKey: "cost", header: "成本" }
]

export function TokenStatisticsPage() {
  const statsQuery = useQuery({
    queryKey: ["usage-statistics"],
    queryFn: async () => unwrap(await getUsageStatistics({ days: 30 })),
    retry: false
  })
  const recordsQuery = useQuery({
    queryKey: ["usage-records"],
    queryFn: async () => unwrap(await getUsageRecords({ limit: 20 })),
    retry: false
  })

  const stats = statsQuery.data
  const records = recordsQuery.data?.records || []

  return (
    <div>
      <PageHeader title="Token使用统计" description="Token使用情况、成本分析和统计图表。" />
      <section className="mb-6 grid gap-4 md:grid-cols-4">
        <Metric title="总请求数" value={stats?.total_requests || 0} />
        <Metric title="总Token数" value={(stats?.total_input_tokens || 0) + (stats?.total_output_tokens || 0)} />
        <Metric title="总成本" value={`¥${Number(stats?.total_cost || 0).toFixed(2)}`} />
        <Metric title="平均成本" value={`¥${Number(stats?.total_requests ? stats.total_cost / stats.total_requests : 0).toFixed(2)}`} />
      </section>
      <div className="mb-6 grid gap-6 lg:grid-cols-2">
        <EChartPanel
          empty={!records.length}
          option={{
            tooltip: {},
            xAxis: { type: "category", data: records.map((item) => item.model_name) },
            yAxis: { type: "value" },
            series: [{ type: "bar", data: records.map((item) => item.input_tokens + item.output_tokens) }]
          }}
        />
        <EChartPanel
          empty={!records.length}
          option={{
            tooltip: {},
            xAxis: { type: "category", data: records.map((item) => item.provider) },
            yAxis: { type: "value" },
            series: [{ type: "bar", data: records.map((item) => item.cost) }]
          }}
        />
      </div>
      <DataTable columns={columns} data={records} loading={recordsQuery.isLoading} emptyText="暂无Token使用记录" />
    </div>
  )
}

function Metric({ title, value }: { title: string; value: string | number }) {
  return (
    <Card>
      <CardContent className="p-4">
        <div className="text-sm text-muted-foreground">{title}</div>
        <div className="mt-2 text-2xl font-semibold">{value}</div>
      </CardContent>
    </Card>
  )
}
