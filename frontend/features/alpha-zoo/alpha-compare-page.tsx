"use client"

import Link from "next/link"
import { useSearchParams } from "next/navigation"
import { useEffect, useMemo, useState } from "react"
import { ArrowLeft, Play } from "lucide-react"

import { PageHeader } from "@/components/feedback/page-header"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { alphaZooApi, type AlphaJob } from "@/libs/api/alpha-zoo"
import { useAppStore, type AppLanguage } from "@/stores/app-store"

const COPY = {
  "zh-CN": {
    title: "Alpha 因子对比",
    description: "对选中的多个 Alpha 因子运行同一组股票和时间区间的输出覆盖度对比。",
    back: "返回 Alpha 因子库",
    alphaIds: "Alpha IDs",
    symbols: "候选股票",
    start: "开始日期",
    end: "结束日期",
    run: "运行对比",
    result: "对比结果",
    status: "状态",
    rows: "结果行数",
    factor: "因子",
    outputRows: "输出行数",
    columns: "列数",
    nonNull: "非空值",
    noRows: "暂无结果",
    error: "因子对比失败",
    needTwo: "至少需要两个 Alpha ID"
  },
  "en-US": {
    title: "Alpha compare",
    description: "Compare selected alpha factors over the same symbols and date range using backend output coverage metrics.",
    back: "Back to Alpha Zoo",
    alphaIds: "Alpha IDs",
    symbols: "Symbols",
    start: "Start date",
    end: "End date",
    run: "Run compare",
    result: "Compare result",
    status: "Status",
    rows: "Rows",
    factor: "Factor",
    outputRows: "Output rows",
    columns: "Columns",
    nonNull: "Non-null values",
    noRows: "No result yet",
    error: "Compare failed",
    needTwo: "At least two Alpha IDs are required"
  }
} satisfies Record<AppLanguage, Record<string, string>>

type ResultRow = {
  factor_id?: string
  rows?: number
  columns?: number
  non_null_values?: number
}

function parseAlphaIdsParam(ids: string | null) {
  return (ids || "").split(",").map(decodeURIComponent).filter(Boolean).join(",")
}

export function AlphaComparePage() {
  const language = useAppStore((state) => state.language)
  const copy = COPY[language]
  const searchParams = useSearchParams()
  const [alphaIdsText, setAlphaIdsText] = useState(() => parseAlphaIdsParam(searchParams.get("ids")))
  const [symbols, setSymbols] = useState("600519,000001,300750")
  const [startDate, setStartDate] = useState("2026-06-01")
  const [endDate, setEndDate] = useState("2026-06-03")
  const [running, setRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [job, setJob] = useState<AlphaJob | null>(null)

  useEffect(() => {
    const nextAlphaIdsText = parseAlphaIdsParam(searchParams.get("ids"))
    if (nextAlphaIdsText !== alphaIdsText) {
      queueMicrotask(() => setAlphaIdsText(nextAlphaIdsText))
    }
  }, [alphaIdsText, searchParams])

  const alphaIds = useMemo(() => alphaIdsText.split(",").map((item) => item.trim()).filter(Boolean), [alphaIdsText])
  const rows = useMemo(() => {
    const result = job?.result as { rows?: ResultRow[] } | undefined
    return result?.rows || []
  }, [job])

  const runCompare = async () => {
    if (alphaIds.length < 2) {
      setError(copy.needTwo)
      return
    }
    setRunning(true)
    setError(null)
    setJob(null)
    try {
      const response = await alphaZooApi.compare({
        alpha_ids: alphaIds,
        symbols: symbols.split(",").map((item) => item.trim()).filter(Boolean),
        start_date: startDate || undefined,
        end_date: endDate || undefined
      })
      setJob(response.data)
    } catch (err) {
      setError(err instanceof Error ? err.message : copy.error)
    } finally {
      setRunning(false)
    }
  }

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <PageHeader title={copy.title} description={copy.description} />

      <Link href="/alpha-zoo" className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground">
        <ArrowLeft className="size-4" />{copy.back}
      </Link>

      <Card>
        <CardHeader><CardTitle className="text-base">{copy.run}</CardTitle></CardHeader>
        <CardContent className="grid gap-4 lg:grid-cols-[minmax(280px,1fr)_minmax(220px,0.7fr)_160px_160px_auto] lg:items-end">
          <div className="grid gap-2">
            <Label>{copy.alphaIds}</Label>
            <Input value={alphaIdsText} onChange={(event) => setAlphaIdsText(event.target.value)} placeholder="alpha101_001,alpha101_002" />
          </div>
          <div className="grid gap-2">
            <Label>{copy.symbols}</Label>
            <Input value={symbols} onChange={(event) => setSymbols(event.target.value)} />
          </div>
          <div className="grid gap-2">
            <Label>{copy.start}</Label>
            <Input value={startDate} onChange={(event) => setStartDate(event.target.value)} />
          </div>
          <div className="grid gap-2">
            <Label>{copy.end}</Label>
            <Input value={endDate} onChange={(event) => setEndDate(event.target.value)} />
          </div>
          <Button onClick={runCompare} disabled={running || alphaIds.length < 2}>
            <Play className="mr-2 size-4" />{running ? "..." : copy.run}
          </Button>
        </CardContent>
      </Card>

      <div className="grid gap-4 md:grid-cols-2">
        <StatCard label={copy.status} value={job?.status || "-"} />
        <StatCard label={copy.rows} value={String(rows.length || 0)} />
      </div>

      {error ? <div className="rounded-md border border-destructive/40 bg-destructive/5 p-3 text-sm text-destructive">{error}</div> : null}

      <Card>
        <CardHeader><CardTitle className="text-base">{copy.result}</CardTitle></CardHeader>
        <CardContent>
          <div className="overflow-x-auto rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{copy.factor}</TableHead>
                  <TableHead className="text-right">{copy.outputRows}</TableHead>
                  <TableHead className="text-right">{copy.columns}</TableHead>
                  <TableHead className="text-right">{copy.nonNull}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.length ? rows.map((row) => (
                  <TableRow key={row.factor_id}>
                    <TableCell className="font-mono text-xs">{row.factor_id}</TableCell>
                    <TableCell className="text-right font-mono text-xs">{row.rows ?? "-"}</TableCell>
                    <TableCell className="text-right font-mono text-xs">{row.columns ?? "-"}</TableCell>
                    <TableCell className="text-right font-mono text-xs">{row.non_null_values ?? "-"}</TableCell>
                  </TableRow>
                )) : (
                  <TableRow><TableCell colSpan={4} className="py-8 text-center text-muted-foreground">{copy.noRows}</TableCell></TableRow>
                )}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}

function StatCard({ label, value }: { label: string; value: string }) {
  return (
    <Card>
      <CardContent className="p-4">
        <div className="text-xs text-muted-foreground">{label}</div>
        <div className="mt-1 text-lg font-semibold">{value}</div>
      </CardContent>
    </Card>
  )
}
