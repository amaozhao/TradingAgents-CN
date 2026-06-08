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
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { alphaZooApi, type AlphaFactor, type AlphaJob } from "@/libs/api/alpha-zoo"
import { useAppStore, type AppLanguage } from "@/stores/app-store"

const ZOOS = [
  { id: "qlib158", label: { "zh-CN": "Qlib 158", "en-US": "Qlib 158" } },
  { id: "alpha101", label: { "zh-CN": "Kakushadze 101", "en-US": "Kakushadze 101" } },
  { id: "gtja191", label: { "zh-CN": "GTJA 191", "en-US": "GTJA 191" } },
  { id: "academic", label: { "zh-CN": "学术异常因子", "en-US": "Academic" } }
]

const COPY = {
  "zh-CN": {
    title: "Alpha 基准测试",
    description: "选择一个因子库，批量运行当前后端支持的 compare/coverage 基准任务。",
    back: "返回 Alpha 因子库",
    zoo: "因子库",
    symbols: "候选股票",
    start: "开始日期",
    end: "结束日期",
    run: "运行基准测试",
    loading: "正在加载因子...",
    count: "待运行因子数",
    result: "运行结果",
    status: "状态",
    rows: "结果行数",
    factor: "因子",
    nonNull: "非空值",
    columns: "列数",
    error: "基准测试失败",
    noRows: "暂无结果"
  },
  "en-US": {
    title: "Alpha benchmark",
    description: "Select a zoo and run the backend-supported compare/coverage benchmark in batch.",
    back: "Back to Alpha Zoo",
    zoo: "Zoo",
    symbols: "Symbols",
    start: "Start date",
    end: "End date",
    run: "Run benchmark",
    loading: "Loading factors...",
    count: "Factors to run",
    result: "Result",
    status: "Status",
    rows: "Rows",
    factor: "Factor",
    nonNull: "Non-null values",
    columns: "Columns",
    error: "Benchmark failed",
    noRows: "No result yet"
  }
} satisfies Record<AppLanguage, Record<string, string>>

type ResultRow = {
  factor_id?: string
  rows?: number
  columns?: number
  non_null_values?: number
}

export function AlphaBenchPage() {
  const language = useAppStore((state) => state.language)
  const copy = COPY[language]
  const searchParams = useSearchParams()
  const [zoo, setZoo] = useState("alpha101")
  const [symbols, setSymbols] = useState("600519,000001,300750")
  const [startDate, setStartDate] = useState("2026-06-01")
  const [endDate, setEndDate] = useState("2026-06-03")
  const [factors, setFactors] = useState<AlphaFactor[]>([])
  const [loadingFactors, setLoadingFactors] = useState(false)
  const [running, setRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [job, setJob] = useState<AlphaJob | null>(null)

  useEffect(() => {
    const requestedZoo = searchParams.get("zoo")
    if (requestedZoo && ZOOS.some((item) => item.id === requestedZoo)) {
      setZoo(requestedZoo)
    }
  }, [searchParams])

  useEffect(() => {
    let alive = true
    setLoadingFactors(true)
    setError(null)
    alphaZooApi
      .list({ zoo, limit: 1000 })
      .then((response) => {
        if (alive) setFactors(response.data.items || response.data.alphas || [])
      })
      .catch((err: unknown) => {
        if (alive) setError(err instanceof Error ? err.message : copy.error)
      })
      .finally(() => {
        if (alive) setLoadingFactors(false)
      })
    return () => {
      alive = false
    }
  }, [copy.error, zoo])

  const rows = useMemo(() => {
    const result = job?.result as { rows?: ResultRow[] } | undefined
    return result?.rows || []
  }, [job])

  const runBenchmark = async () => {
    const alphaIds = factors.map((factor) => factor.id)
    if (!alphaIds.length) return
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
        <CardHeader>
          <CardTitle className="text-base">{copy.run}</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-4 lg:grid-cols-[180px_minmax(240px,1fr)_160px_160px_auto] lg:items-end">
          <div className="grid gap-2">
            <Label>{copy.zoo}</Label>
            <Select value={zoo} onValueChange={setZoo}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>{ZOOS.map((option) => <SelectItem key={option.id} value={option.id}>{option.label[language]}</SelectItem>)}</SelectContent>
            </Select>
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
          <Button onClick={runBenchmark} disabled={running || loadingFactors || factors.length === 0}>
            <Play className="mr-2 size-4" />{running ? "..." : copy.run}
          </Button>
        </CardContent>
      </Card>

      <div className="grid gap-4 md:grid-cols-3">
        <StatCard label={copy.count} value={loadingFactors ? copy.loading : String(factors.length)} />
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
                  <TableHead className="text-right">{copy.rows}</TableHead>
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
