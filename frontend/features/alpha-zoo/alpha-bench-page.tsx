"use client"

import Link from "next/link"
import { useSearchParams } from "next/navigation"
import { useEffect, useMemo, useRef, useState } from "react"
import { ArrowLeft, Loader2, Play } from "lucide-react"

import { PageHeader } from "@/components/feedback/page-header"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Skeleton } from "@/components/ui/skeleton"
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
    description: "检查因子是否能在当前后端数据面板上稳定输出有效值。",
    back: "返回 Alpha 因子库",
    zoo: "因子库",
    factors: "选择因子",
    selectAll: "全选",
    clearSelection: "清空",
    selectedCount: "已选",
    symbols: "候选股票",
    start: "开始日期",
    end: "结束日期",
    run: "运行覆盖检查",
    running: "运行中",
    loading: "正在加载因子...",
    count: "待运行因子数",
    mode: "测试模式",
    singleMode: "单因子",
    batchMode: "因子库批量",
    result: "运行结果",
    status: "状态",
    validDates: "有效日期数",
    symbolCount: "股票数量",
    validValues: "有效因子值",
    coverage: "覆盖率",
    computable: "可计算",
    noValidOutput: "无有效输出",
    factor: "因子",
    error: "基准测试失败",
    noRows: "暂无结果",
    coverageNotice: "当前是因子输出覆盖检查：用于确认因子在后端测试数据面板上能否算出有效值，不是收益回测，也不代表投资表现。"
  },
  "en-US": {
    title: "Alpha benchmark",
    description: "Check whether factors can produce valid values on the current backend data panel.",
    back: "Back to Alpha Zoo",
    zoo: "Zoo",
    factors: "Select factors",
    selectAll: "Select all",
    clearSelection: "Clear",
    selectedCount: "Selected",
    symbols: "Symbols",
    start: "Start date",
    end: "End date",
    run: "Run coverage check",
    running: "Running",
    loading: "Loading factors...",
    count: "Factors to run",
    mode: "Mode",
    singleMode: "Single factor",
    batchMode: "Zoo batch",
    result: "Result",
    status: "Status",
    validDates: "Valid dates",
    symbolCount: "Symbols",
    validValues: "Valid values",
    coverage: "Coverage",
    computable: "Computable",
    noValidOutput: "No valid output",
    factor: "Factor",
    error: "Benchmark failed",
    noRows: "No result yet",
    coverageNotice: "This is a factor output coverage check: it confirms whether the factor can produce valid values on the backend test data panel. It is not a returns backtest and does not represent investment performance."
  }
} satisfies Record<AppLanguage, Record<string, string>>

type ResultRow = {
  factor_id?: string
  rows?: number
  columns?: number
  non_null_values?: number
  classification?: string
}

function validZoo(value: string | null) {
  return value && ZOOS.some((item) => item.id === value) ? value : null
}

function parseAlphaId(value: string | null) {
  return value?.trim() || ""
}

function splitSymbols(value: string) {
  return value.split(",").map((item) => item.trim()).filter(Boolean)
}

function coverageRate(row: ResultRow) {
  const denominator = (row.rows || 0) * (row.columns || 0)
  return denominator > 0 && typeof row.non_null_values === "number" ? row.non_null_values / denominator : null
}

function formatPercent(value: number | null) {
  return value === null ? "-" : `${(value * 100).toFixed(1)}%`
}

function normalizeRows(job: AlphaJob | null): ResultRow[] {
  const result = job?.result as {
    rows?: ResultRow[]
    summary?: ResultRow
    classification?: string
  } | undefined

  if (result?.summary) {
    return [{ ...result.summary, classification: result.classification }]
  }
  return result?.rows || []
}

export function AlphaBenchPage() {
  const language = useAppStore((state) => state.language)
  const copy = COPY[language]
  const searchParams = useSearchParams()
  const initialUrlZoo = validZoo(searchParams.get("zoo"))
  const initialUrlAlphaId = parseAlphaId(searchParams.get("alpha_id"))
  const appliedUrlStateRef = useRef({ zoo: initialUrlZoo, alphaId: initialUrlAlphaId })
  const [zoo, setZoo] = useState(() => initialUrlZoo || "alpha101")
  const [selectedIds, setSelectedIds] = useState<Set<string>>(() => {
    return initialUrlAlphaId ? new Set([initialUrlAlphaId]) : new Set()
  })
  const [symbols, setSymbols] = useState("600519,000001,300750")
  const [startDate, setStartDate] = useState("2025-01-01")
  const [endDate, setEndDate] = useState("2026-06-03")
  const [factors, setFactors] = useState<AlphaFactor[]>([])
  const [loadingFactors, setLoadingFactors] = useState(false)
  const [running, setRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [job, setJob] = useState<AlphaJob | null>(null)

  useEffect(() => {
    const requestedZoo = validZoo(searchParams.get("zoo"))
    const requestedAlphaId = parseAlphaId(searchParams.get("alpha_id"))
    if (
      requestedZoo === appliedUrlStateRef.current.zoo &&
      requestedAlphaId === appliedUrlStateRef.current.alphaId
    ) {
      return
    }
    appliedUrlStateRef.current = { zoo: requestedZoo, alphaId: requestedAlphaId }
    queueMicrotask(() => {
      if (requestedZoo) setZoo(requestedZoo)
      setSelectedIds(requestedAlphaId ? new Set([requestedAlphaId]) : new Set())
      setJob(null)
    })
  }, [searchParams])

  useEffect(() => {
    let alive = true

    const loadFactors = async () => {
      setLoadingFactors(true)
      setError(null)
      try {
        const response = await alphaZooApi.list({ zoo, limit: 1000 })
        if (alive) setFactors(response.data.items || response.data.alphas || [])
      } catch (err) {
        if (alive) setError(err instanceof Error ? err.message : copy.error)
      } finally {
        if (alive) setLoadingFactors(false)
      }
    }

    void loadFactors()
    return () => {
      alive = false
    }
  }, [copy.error, zoo])

  const rows = useMemo(() => normalizeRows(job), [job])
  const selectedAlphaIds = useMemo(() => {
    const ordered = factors.map((factor) => factor.id).filter((id) => selectedIds.has(id))
    const extras = Array.from(selectedIds).filter((id) => !ordered.includes(id))
    return [...ordered, ...extras]
  }, [factors, selectedIds])
  const runAlphaIds = selectedAlphaIds.length ? selectedAlphaIds : factors.map((factor) => factor.id)
  const isSingleFactorMode = selectedAlphaIds.length === 1
  const maxCoverage = useMemo(() => {
    const values = rows.map((row) => coverageRate(row)).filter((value): value is number => value !== null)
    return values.length ? Math.max(...values) : null
  }, [rows])

  const toggleFactor = (factorId: string) => {
    setSelectedIds((current) => {
      const next = new Set(current)
      if (next.has(factorId)) next.delete(factorId)
      else next.add(factorId)
      return next
    })
  }

  const changeZoo = (nextZoo: string) => {
    setZoo(nextZoo)
    setSelectedIds(new Set())
    setJob(null)
    setError(null)
  }

  const runBenchmark = async () => {
    if (running) return
    const cleanSymbols = splitSymbols(symbols)
    if (!runAlphaIds.length) return
    setRunning(true)
    setError(null)
    setJob(null)
    try {
      const response = selectedAlphaIds.length === 1
        ? await alphaZooApi.bench({
          alpha_id: selectedAlphaIds[0],
          symbols: cleanSymbols,
          start_date: startDate || undefined,
          end_date: endDate || undefined
        })
        : await alphaZooApi.compare({
          alpha_ids: runAlphaIds,
          symbols: cleanSymbols,
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

  const canRun = runAlphaIds.length > 0 && !(loadingFactors && selectedAlphaIds.length === 0)

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <PageHeader title={copy.title} description={copy.description} />

      <Link href="/alpha-zoo" className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground">
        <ArrowLeft className="size-4" />{copy.back}
      </Link>

      <div className="rounded-md border border-blue-200 bg-blue-50 p-3 text-sm leading-relaxed text-blue-900 dark:border-blue-900/60 dark:bg-blue-950/30 dark:text-blue-100">
        {copy.coverageNotice}
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">{copy.run}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-5">
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-[220px_minmax(280px,1fr)_180px_180px_auto] xl:items-end">
            <div className="grid gap-2">
              <Label>{copy.zoo}</Label>
              <Select value={zoo} onValueChange={changeZoo}>
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
            <div className="flex md:col-span-2 xl:col-span-1">
              <Button
                aria-disabled={running}
                className={`w-full ${running ? "animate-pulse shadow-lg ring-2 ring-primary/25" : ""}`}
                onClick={runBenchmark}
                disabled={!canRun}
              >
                {running ? <Loader2 className="mr-2 size-4 animate-spin" /> : <Play className="mr-2 size-4" />}
                {running ? copy.running : copy.run}
              </Button>
            </div>
          </div>

          <div className="rounded-md border bg-muted/20 p-3">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="text-sm font-medium">{copy.factors}</div>
              <div className="flex items-center gap-2">
                <span className="text-xs text-muted-foreground">{copy.selectedCount}: {selectedAlphaIds.length || factors.length}</span>
                <Button type="button" variant="outline" size="sm" onClick={() => setSelectedIds(new Set(factors.map((factor) => factor.id)))} disabled={loadingFactors || factors.length === 0}>
                  {copy.selectAll}
                </Button>
                <Button type="button" variant="outline" size="sm" onClick={() => setSelectedIds(new Set())} disabled={selectedAlphaIds.length === 0}>
                  {copy.clearSelection}
                </Button>
              </div>
            </div>
            <div className="mt-3 grid max-h-56 gap-2 overflow-y-auto pr-1 sm:grid-cols-2 lg:grid-cols-3">
              {loadingFactors ? (
                <div className="text-sm text-muted-foreground">{copy.loading}</div>
              ) : factors.map((factor) => (
                <label key={factor.id} className="flex min-h-10 cursor-pointer items-start gap-2 rounded-md border bg-background px-3 py-2 text-sm hover:bg-muted/50">
                  <input
                    type="checkbox"
                    className="mt-0.5 size-4 shrink-0"
                    checked={selectedIds.has(factor.id)}
                    onChange={() => toggleFactor(factor.id)}
                  />
                  <span className="min-w-0">
                    <span className="block truncate font-mono text-xs">{factor.id}</span>
                    <span className="block truncate text-xs text-muted-foreground">{factor.nickname || factor.name}</span>
                  </span>
                </label>
              ))}
            </div>
          </div>
        </CardContent>
      </Card>

      <div className="grid gap-4 md:grid-cols-4">
        <StatCard label={copy.mode} value={isSingleFactorMode ? copy.singleMode : copy.batchMode} />
        <StatCard label={copy.count} value={loadingFactors && !selectedAlphaIds.length ? copy.loading : String(runAlphaIds.length)} />
        <StatCard label={copy.status} value={job?.status || "-"} />
        <StatCard label={copy.coverage} value={formatPercent(maxCoverage)} />
      </div>

      {error ? <div className="rounded-md border border-destructive/40 bg-destructive/5 p-3 text-sm text-destructive">{error}</div> : null}

      <Card className={running ? "border-primary/40 shadow-sm" : ""}>
        <CardHeader><CardTitle className="text-base">{copy.result}</CardTitle></CardHeader>
        <CardContent>
          <div className="overflow-x-auto rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{copy.factor}</TableHead>
                  <TableHead>{copy.status}</TableHead>
                  <TableHead className="text-right">{copy.validDates}</TableHead>
                  <TableHead className="text-right">{copy.symbolCount}</TableHead>
                  <TableHead className="text-right">{copy.validValues}</TableHead>
                  <TableHead className="text-right">{copy.coverage}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {running ? (
                  Array.from({ length: 3 }).map((_, index) => (
                    <TableRow key={`loading-${index}`} data-testid="alpha-bench-loading-row">
                      <TableCell><Skeleton className="h-4 w-36" /></TableCell>
                      <TableCell><Skeleton className="h-4 w-20" /></TableCell>
                      <TableCell className="text-right"><Skeleton className="ml-auto h-4 w-12" /></TableCell>
                      <TableCell className="text-right"><Skeleton className="ml-auto h-4 w-12" /></TableCell>
                      <TableCell className="text-right"><Skeleton className="ml-auto h-4 w-16" /></TableCell>
                      <TableCell className="text-right"><Skeleton className="ml-auto h-4 w-14" /></TableCell>
                    </TableRow>
                  ))
                ) : rows.length ? rows.map((row) => (
                  <TableRow key={row.factor_id}>
                    <TableCell className="font-mono text-xs">{row.factor_id}</TableCell>
                    <TableCell>{(row.non_null_values || 0) > 0 ? copy.computable : copy.noValidOutput}</TableCell>
                    <TableCell className="text-right font-mono text-xs">{row.rows ?? "-"}</TableCell>
                    <TableCell className="text-right font-mono text-xs">{row.columns ?? "-"}</TableCell>
                    <TableCell className="text-right font-mono text-xs">{row.non_null_values ?? "-"}</TableCell>
                    <TableCell className="text-right font-mono text-xs">{formatPercent(coverageRate(row))}</TableCell>
                  </TableRow>
                )) : (
                  <TableRow><TableCell colSpan={6} className="py-8 text-center text-muted-foreground">{copy.noRows}</TableCell></TableRow>
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
