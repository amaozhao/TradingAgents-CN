"use client"

import { useQuery } from "@tanstack/react-query"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { toast } from "sonner"

import { PageHeader } from "@/components/feedback/page-header"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { downloadReport, fetchReportDetail } from "@/features/reports/report-api"
import { buildReportSectionGroups, type ReportSectionItem } from "@/features/reports/report-section-meta"
import { MarkdownRenderer } from "@/features/learning/markdown-renderer"
import { formatDateTime } from "@/libs/utils/datetime"

export function ReportDetailPage({ id }: { id: string }) {
  const router = useRouter()
  const reportQuery = useQuery({
    queryKey: ["report-detail", id],
    queryFn: () => fetchReportDetail(id),
    retry: false
  })

  const report = reportQuery.data
  const sectionGroups = report ? buildReportSectionGroups(report.reports || {}) : []
  const reportFilename = report ? `${report.stock_symbol}_analysis_report.md` : "analysis-report.md"

  const handleDownload = async () => {
    try {
      await downloadReport(id, "markdown", reportFilename)
      toast.success("报告下载成功")
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "报告下载失败")
    }
  }

  const handleApplyToTrade = () => {
    if (!report?.stock_symbol) {
      toast.error("报告缺少股票代码")
      return
    }
    const recommendation = String(report.recommendation || "").toLowerCase()
    const side = recommendation.includes("卖") || recommendation.includes("减") || recommendation.includes("sell") ? "sell" : "buy"
    router.push(`/paper?code=${encodeURIComponent(report.stock_symbol)}&side=${side}&quantity=100&analysis_id=${encodeURIComponent(report.id)}`)
  }

  return (
    <div>
      <PageHeader
        title={report ? `${report.stock_name || report.stock_symbol} 分析报告` : "分析报告"}
        description={report?.created_at ? `创建时间：${formatDateTime(report.created_at)}` : "报告详情"}
        actions={
          <div className="flex flex-wrap gap-2">
            {report ? <Button variant="outline" onClick={handleApplyToTrade}>应用到交易</Button> : null}
            {report ? <Button variant="outline" onClick={handleDownload}>下载报告</Button> : null}
            <Button asChild variant="outline">
              <Link href="/reports">返回列表</Link>
            </Button>
          </div>
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
              <Metric label="置信度" value={formatConfidence(report.confidence_score)} />
            </CardContent>
          </Card>
          {report.summary || sectionGroups.length > 0 ? (
            <div className="space-y-8">
              {report.summary ? (
                <ReportGroup
                  title="总览"
                  description="先看摘要和最终结论，快速判断这份报告的核心立场。"
                  sections={sectionGroups.find((group) => group.key === "overview")?.sections || []}
                  summary={report.summary}
                />
              ) : null}
              {sectionGroups
                .filter((group) => report.summary ? group.key !== "overview" : true)
                .map((group) => (
                  <ReportGroup
                    key={group.key}
                    title={group.title}
                    description={group.description}
                    sections={group.sections}
                  />
                ))}
            </div>
          ) : null}
        </div>
      ) : (
        <Card><CardContent className="p-6 text-sm text-muted-foreground">报告不存在或加载失败。</CardContent></Card>
      )}
    </div>
  )
}

function ReportGroup({
  title,
  description,
  sections,
  summary
}: {
  title: string
  description: string
  sections: ReportSectionItem[]
  summary?: string
}) {
  if (!summary && sections.length === 0) return null

  return (
    <section className="space-y-4">
      <div className="border-b pb-3">
        <h2 className="text-xl font-semibold tracking-normal">{title}</h2>
        <p className="mt-1 text-sm text-muted-foreground">{description}</p>
      </div>
      <div className="grid gap-4">
        {summary ? (
          <ReportSection
            section={{
              key: "summary",
              title: "报告摘要",
              enTitle: "Report Summary",
              description: "报告自动摘要。",
              content: summary,
              group: "overview",
              order: 0
            }}
          />
        ) : null}
        {sections.map((section) => (
          <ReportSection key={section.key} section={section} />
        ))}
      </div>
    </section>
  )
}

function ReportSection({ section }: { section: ReportSectionItem }) {
  return (
    <Card>
      <CardHeader className="space-y-2">
        <div>
          <h3 className="text-base font-semibold tracking-normal">{section.title}</h3>
          <p className="mt-1 text-sm text-muted-foreground">{section.description}</p>
        </div>
      </CardHeader>
      <CardContent>
        {typeof section.content === "string" ? (
          <MarkdownRenderer content={section.content} />
        ) : (
          <pre className="overflow-x-auto rounded-md bg-muted p-4 text-sm">{JSON.stringify(section.content, null, 2)}</pre>
        )}
      </CardContent>
    </Card>
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

function formatConfidence(value?: number) {
  const numeric = Number(value || 0)
  const percent = numeric > 0 && numeric <= 1 ? numeric * 100 : numeric
  return `${Math.round(percent)}%`
}
