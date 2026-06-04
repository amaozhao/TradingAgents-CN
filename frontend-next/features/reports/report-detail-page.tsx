"use client"

import { useQuery } from "@tanstack/react-query"
import Link from "next/link"

import { PageHeader } from "@/components/feedback/page-header"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { fetchReportDetail } from "@/features/reports/report-api"
import { MarkdownRenderer } from "@/features/learning/markdown-renderer"
import { formatDateTime } from "@/libs/utils/datetime"

export function ReportDetailPage({ id }: { id: string }) {
  const reportQuery = useQuery({
    queryKey: ["report-detail", id],
    queryFn: () => fetchReportDetail(id),
    retry: false
  })

  const report = reportQuery.data

  return (
    <div>
      <PageHeader
        title={report ? `${report.stock_name || report.stock_symbol} 分析报告` : "分析报告"}
        description={report?.created_at ? `创建时间：${formatDateTime(report.created_at)}` : "报告详情"}
        actions={
          <Button asChild variant="outline">
            <Link href="/reports">返回列表</Link>
          </Button>
        }
      />
      {reportQuery.isLoading ? (
        <Card><CardContent className="p-6 text-sm text-muted-foreground">加载中...</CardContent></Card>
      ) : report ? (
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                {report.stock_symbol}
                <Badge>{formatStatus(report.status)}</Badge>
              </CardTitle>
            </CardHeader>
            <CardContent className="grid gap-4 md:grid-cols-3">
              <Metric label="分析参考" value={report.recommendation || "暂无"} />
              <Metric label="风险等级" value={report.risk_level || "中等"} />
              <Metric label="置信度" value={`${Number(report.confidence_score || 0)}%`} />
            </CardContent>
          </Card>
          {report.summary ? (
            <Card>
              <CardHeader><CardTitle>报告摘要</CardTitle></CardHeader>
              <CardContent><MarkdownRenderer content={report.summary} /></CardContent>
            </Card>
          ) : null}
          {Object.entries(report.reports || {}).map(([key, value]) => (
            <Card key={key}>
              <CardHeader><CardTitle>{formatModuleName(key)}</CardTitle></CardHeader>
              <CardContent>
                {typeof value === "string" ? (
                  <MarkdownRenderer content={value} />
                ) : (
                  <pre className="overflow-x-auto rounded-md bg-muted p-4 text-sm">{JSON.stringify(value, null, 2)}</pre>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      ) : (
        <Card><CardContent className="p-6 text-sm text-muted-foreground">报告不存在或加载失败。</CardContent></Card>
      )}
    </div>
  )
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border p-4">
      <div className="text-sm text-muted-foreground">{label}</div>
      <div className="mt-2 font-medium">{value}</div>
    </div>
  )
}

function formatStatus(status?: string) {
  const map: Record<string, string> = { completed: "已完成", failed: "失败", generating: "生成中" }
  return status ? map[status] ?? status : "-"
}

function formatModuleName(key: string) {
  const map: Record<string, string> = {
    market_report: "市场分析",
    fundamentals_report: "基本面分析",
    news_report: "新闻分析",
    sentiment_report: "情绪分析",
    trader_investment_plan: "交易计划"
  }
  return map[key] ?? key
}
