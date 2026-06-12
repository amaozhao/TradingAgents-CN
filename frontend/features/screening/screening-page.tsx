"use client"

import Link from "next/link"
import { useMemo, useState } from "react"
import { useRouter } from "next/navigation"
import { useMutation, useQuery } from "@tanstack/react-query"
import { BarChart3, Download, RefreshCw, Search, Star } from "lucide-react"
import { toast } from "sonner"

import { EmptyState } from "@/components/feedback/empty-state"
import { PageHeader } from "@/components/feedback/page-header"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { favoritesApi } from "@/libs/api/favorites"
import { screeningApi, type ScreeningRunItem } from "@/libs/api/screening"
import { getCurrentDataSource } from "@/libs/api/sync"
import { batchAgentHref, stockAgentHref } from "@/libs/routes/agent"

function unwrap<T>(response: T | { data: T }): T {
  return response && typeof response === "object" && "data" in response ? response.data : response
}

const capRangeMap: Record<string, [number, number]> = {
  small: [0, 100 * 10000],
  medium: [100 * 10000, 500 * 10000],
  large: [500 * 10000, Number.MAX_SAFE_INTEGER]
}

const volumeRangeMap: Record<string, [number, number]> = {
  high: [1_000_000_000, Number.MAX_SAFE_INTEGER],
  medium: [300_000_000, 1_000_000_000],
  low: [0, 300_000_000]
}

export function ScreeningPage() {
  const router = useRouter()
  const [filters, setFilters] = useState({
    market: "A股",
    industry: [] as string[],
    marketCapRange: "all",
    peMin: "",
    peMax: "",
    pbMin: "",
    pbMax: "",
    roeMin: "",
    roeMax: "",
    changeMin: "",
    changeMax: "",
    volumeLevel: "all"
  })
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)
  const [results, setResults] = useState<ScreeningRunItem[]>([])
  const [selectedCodes, setSelectedCodes] = useState<string[]>([])
  const [hasSearched, setHasSearched] = useState(false)

  const currentSourceQuery = useQuery({ queryKey: ["sync", "current-source"], queryFn: () => getCurrentDataSource().then(unwrap), retry: false })
  const industriesQuery = useQuery({ queryKey: ["screening", "industries"], queryFn: () => screeningApi.getIndustries().then(unwrap), retry: false })
  const favoritesQuery = useQuery({ queryKey: ["favorites"], queryFn: () => favoritesApi.list().then(unwrap), retry: false })

  const runMutation = useMutation({
    mutationFn: () => {
      const children: Array<{ field: string; op: string; value: unknown }> = []
      if (filters.industry.length) children.push({ field: "industry", op: "in", value: filters.industry })
      if (filters.marketCapRange !== "all") children.push({ field: "market_cap", op: "between", value: capRangeMap[filters.marketCapRange] })
      addRange(children, "pe", filters.peMin, filters.peMax, 0, Number.MAX_SAFE_INTEGER)
      addRange(children, "pb", filters.pbMin, filters.pbMax, 0, Number.MAX_SAFE_INTEGER)
      addRange(children, "roe", filters.roeMin, filters.roeMax, 0, 100)
      addRange(children, "pct_chg", filters.changeMin, filters.changeMax, -100, 100)
      if (filters.volumeLevel !== "all") children.push({ field: "amount", op: "between", value: volumeRangeMap[filters.volumeLevel] })

      return screeningApi.run({
        market: "CN",
        date: null,
        adj: "qfq",
        conditions: { logic: "AND", children },
        order_by: [{ field: "market_cap", direction: "desc" }],
        limit: 500,
        offset: 0
      }, { timeout: 120000 }).then(unwrap)
    },
    onSuccess: (data) => {
      setResults(data.items.map(normalizeItem))
      setSelectedCodes([])
      setPage(1)
      setHasSearched(true)
      toast.success(`筛选完成，找到 ${data.items.length} 只股票`)
    },
    onError: (error) => toast.error(error.message)
  })

  const favorites = useMemo(() => new Set((favoritesQuery.data || []).map((item) => item.symbol || item.stock_code).filter(Boolean) as string[]), [favoritesQuery.data])
  const paginatedResults = useMemo(() => results.slice((page - 1) * pageSize, page * pageSize), [page, pageSize, results])
  const totalAmount = useMemo(() => results.reduce((sum, item) => sum + (item.amount || 0), 0), [results])
  const selectedSet = useMemo(() => new Set(selectedCodes), [selectedCodes])
  const industries = industriesQuery.data?.industries || []

  const resetFilters = () => {
    setFilters({
      market: "A股",
      industry: [],
      marketCapRange: "all",
      peMin: "",
      peMax: "",
      pbMin: "",
      pbMax: "",
      roeMin: "",
      roeMax: "",
      changeMin: "",
      changeMax: "",
      volumeLevel: "all"
    })
  }

  const toggleSelectedCode = (code: string, checked: boolean) => {
    setSelectedCodes((current) => checked ? (current.includes(code) ? current : [...current, code]) : current.filter((item) => item !== code))
  }

  const goToBatchAnalysis = () => {
    if (!selectedCodes.length) {
      toast.warning("请先选择要分析的股票")
      return
    }
    router.push(batchAgentHref({ stocks: selectedCodes }))
  }

  const exportResults = () => {
    const blob = new Blob([JSON.stringify(results, null, 2)], { type: "application/json;charset=utf-8" })
    const url = URL.createObjectURL(blob)
    const link = document.createElement("a")
    link.href = url
    link.download = `screening_results_${Date.now()}.json`
    link.click()
    URL.revokeObjectURL(url)
  }

  const toggleFavorite = async (item: ScreeningRunItem) => {
    const code = item.code || item.symbol
    if (!code) return
    try {
      if (favorites.has(code)) {
        await favoritesApi.remove(code)
        toast.success("已取消自选")
      } else {
        await favoritesApi.add({ symbol: code, stock_name: item.name || code, market: item.market || "A股" })
        toast.success("已加入自选")
      }
      void favoritesQuery.refetch()
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "自选操作失败")
    }
  }

  return (
    <div>
      <PageHeader
        title="股票筛选"
        description="通过多维度筛选条件，快速找到符合投资策略的优质股票"
        actions={
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" onClick={goToBatchAnalysis} disabled={!selectedCodes.length}>
              <BarChart3 className="mr-2 size-4" />
              批量分析 ({selectedCodes.length})
            </Button>
            <Button onClick={() => runMutation.mutate()} disabled={runMutation.isPending}>
              <Search className="mr-2 size-4" />
              开始筛选
            </Button>
          </div>
        }
      />
      <Card>
        <CardHeader className="flex-row items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-3">
            <CardTitle>筛选条件</CardTitle>
            {currentSourceQuery.data ? (
              <Badge variant="secondary">当前数据源：{currentSourceQuery.data.name}</Badge>
            ) : (
              <Badge variant="outline">无可用数据源</Badge>
            )}
          </div>
          <Button variant="ghost" size="sm" onClick={resetFilters}>
            <RefreshCw className="mr-2 size-4" />
            重置
          </Button>
        </CardHeader>
        <CardContent className="space-y-5">
          <div className="grid gap-4 md:grid-cols-3">
            <div className="grid gap-2">
              <Label>市场类型</Label>
              <Select value={filters.market} onValueChange={(market) => setFilters((value) => ({ ...value, market }))} disabled>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent><SelectItem value="A股">A股</SelectItem></SelectContent>
              </Select>
            </div>
            <div className="grid gap-2">
              <Label>行业分类</Label>
              <Select value="select" onValueChange={(industry) => {
                if (industry !== "select" && !filters.industry.includes(industry)) setFilters((value) => ({ ...value, industry: [...value.industry, industry] }))
              }}>
                <SelectTrigger><SelectValue placeholder="选择行业" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="select">选择行业</SelectItem>
                  {industries.map((item) => <SelectItem key={item.value} value={item.value}>{item.label}</SelectItem>)}
                </SelectContent>
              </Select>
              {filters.industry.length ? (
                <div className="flex flex-wrap gap-2">
                  {filters.industry.map((item) => (
                    <button key={item} type="button" className="rounded-md bg-primary/10 px-2 py-1 text-xs" onClick={() => setFilters((value) => ({ ...value, industry: value.industry.filter((industry) => industry !== item) }))}>{item} ×</button>
                  ))}
                </div>
              ) : null}
            </div>
            <SelectField label="市值范围" value={filters.marketCapRange} onValueChange={(marketCapRange) => setFilters((value) => ({ ...value, marketCapRange }))} options={[
              ["all", "全部"],
              ["small", "小盘股 (< 100亿)"],
              ["medium", "中盘股 (100-500亿)"],
              ["large", "大盘股 (> 500亿)"]
            ]} />
          </div>

          <div className="grid gap-4 md:grid-cols-3">
            <RangeField label="市盈率 (PE)" min={filters.peMin} max={filters.peMax} onMin={(peMin) => setFilters((value) => ({ ...value, peMin }))} onMax={(peMax) => setFilters((value) => ({ ...value, peMax }))} />
            <RangeField label="市净率 (PB)" min={filters.pbMin} max={filters.pbMax} onMin={(pbMin) => setFilters((value) => ({ ...value, pbMin }))} onMax={(pbMax) => setFilters((value) => ({ ...value, pbMax }))} />
            <RangeField label="ROE (%)" min={filters.roeMin} max={filters.roeMax} onMin={(roeMin) => setFilters((value) => ({ ...value, roeMin }))} onMax={(roeMax) => setFilters((value) => ({ ...value, roeMax }))} />
          </div>

          <div className="grid gap-4 md:grid-cols-3">
            <RangeField label="涨跌幅 (%)" min={filters.changeMin} max={filters.changeMax} onMin={(changeMin) => setFilters((value) => ({ ...value, changeMin }))} onMax={(changeMax) => setFilters((value) => ({ ...value, changeMax }))} />
            <SelectField label="成交量" value={filters.volumeLevel} onValueChange={(volumeLevel) => setFilters((value) => ({ ...value, volumeLevel }))} options={[
              ["all", "全部"],
              ["high", "活跃 (高成交量)"],
              ["medium", "正常 (中等成交量)"],
              ["low", "清淡 (低成交量)"]
            ]} />
          </div>

          <div className="flex justify-center gap-2">
            <Button onClick={() => runMutation.mutate()} disabled={runMutation.isPending}>
              <Search className="mr-2 size-4" />
              开始筛选
            </Button>
            <Button variant="outline" onClick={resetFilters}>重置条件</Button>
          </div>
        </CardContent>
      </Card>

      <div className="mt-4 grid gap-4 md:grid-cols-3">
        <Card><CardContent className="p-5"><div className="text-sm text-muted-foreground">结果数</div><div className="mt-2 text-2xl font-semibold">{results.length}</div></CardContent></Card>
        <Card><CardContent className="p-5"><div className="text-sm text-muted-foreground">成交额合计</div><div className="mt-2 text-2xl font-semibold">{(totalAmount / 100000000).toFixed(2)} 亿</div></CardContent></Card>
        <Card><CardContent className="p-5"><div className="text-sm text-muted-foreground">排序</div><div className="mt-2 text-2xl font-semibold">市值降序</div></CardContent></Card>
      </div>
      <Card className="mt-6">
        <CardHeader className="flex-row items-center justify-between gap-3">
          <CardTitle>筛选结果 ({results.length}只股票)</CardTitle>
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" onClick={goToBatchAnalysis} disabled={!selectedCodes.length}>批量分析 ({selectedCodes.length})</Button>
            <Button variant="outline" onClick={exportResults} disabled={!results.length}><Download className="mr-2 size-4" />导出结果</Button>
          </div>
        </CardHeader>
        <CardContent>
          {!results.length ? <EmptyState title={hasSearched ? "未找到符合条件的股票" : "暂无筛选结果"} /> : (
            <>
              <div className="overflow-x-auto rounded-md border">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="w-10"><span className="sr-only">选择</span></TableHead>
                      <TableHead>股票代码</TableHead>
                      <TableHead>股票名称</TableHead>
                      <TableHead>行业</TableHead>
                      <TableHead>当前价格</TableHead>
                      <TableHead>涨跌幅</TableHead>
                      <TableHead>市值</TableHead>
                      <TableHead>市盈率</TableHead>
                      <TableHead>市净率</TableHead>
                      <TableHead>ROE(%)</TableHead>
                      <TableHead>板块</TableHead>
                      <TableHead>交易所</TableHead>
                      <TableHead>操作</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {paginatedResults.map((item) => (
                      <TableRow key={item.code}>
                        <TableCell><input aria-label={`选择 ${item.code}`} type="checkbox" checked={selectedSet.has(item.code)} onChange={(event) => toggleSelectedCode(item.code, event.target.checked)} /></TableCell>
                        <TableCell><Link className="text-primary hover:underline" href={`/stocks/${item.code}`}>{item.code}</Link></TableCell>
                        <TableCell>{item.name || "-"}</TableCell>
                        <TableCell>{item.industry || "-"}</TableCell>
                        <TableCell>{item.close ? `¥${item.close.toFixed(2)}` : "-"}</TableCell>
                        <TableCell className={item.pct_chg && item.pct_chg > 0 ? "text-red-600" : item.pct_chg && item.pct_chg < 0 ? "text-emerald-600" : ""}>{item.pct_chg != null ? `${item.pct_chg > 0 ? "+" : ""}${item.pct_chg.toFixed(2)}%` : "-"}</TableCell>
                        <TableCell>{formatMarketCap(item.total_mv)}</TableCell>
                        <TableCell>{item.pe != null ? item.pe.toFixed(2) : "-"}</TableCell>
                        <TableCell>{item.pb != null ? item.pb.toFixed(2) : "-"}</TableCell>
                        <TableCell>{item.roe != null ? `${item.roe.toFixed(2)}%` : "-"}</TableCell>
                        <TableCell>{item.board || "-"}</TableCell>
                        <TableCell>{item.exchange || "-"}</TableCell>
                        <TableCell>
                          <div className="flex gap-2">
                            <Button size="sm" variant="outline" onClick={() => router.push(stockAgentHref({ stock: item.code, market: item.market || "A股" }))}>分析</Button>
                            <Button size="sm" variant="outline" onClick={() => void toggleFavorite(item)}>
                              <Star className="mr-1 size-3" />
                              {favorites.has(item.code) ? "取消自选" : "加入自选"}
                            </Button>
                          </div>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
              <div className="mt-4 flex flex-wrap items-center justify-center gap-3">
                <Button variant="outline" disabled={page <= 1} onClick={() => setPage((value) => Math.max(1, value - 1))}>上一页</Button>
                <span className="text-sm text-muted-foreground">第 {page} 页 / 共 {Math.max(1, Math.ceil(results.length / pageSize))} 页</span>
                <Button variant="outline" disabled={page >= Math.ceil(results.length / pageSize)} onClick={() => setPage((value) => value + 1)}>下一页</Button>
                <Select value={`${pageSize}`} onValueChange={(value) => { setPageSize(Number(value)); setPage(1) }}>
                  <SelectTrigger className="w-28"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="20">20 / 页</SelectItem>
                    <SelectItem value="50">50 / 页</SelectItem>
                    <SelectItem value="100">100 / 页</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

function RangeField({ label, min, max, onMin, onMax }: { label: string; min: string; max: string; onMin: (value: string) => void; onMax: (value: string) => void }) {
  return (
    <div className="grid gap-2">
      <Label>{label}</Label>
      <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-2">
        <Input type="number" placeholder="最小值" value={min} onChange={(event) => onMin(event.target.value)} />
        <span className="text-muted-foreground">-</span>
        <Input type="number" placeholder="最大值" value={max} onChange={(event) => onMax(event.target.value)} />
      </div>
    </div>
  )
}

function SelectField({ label, value, onValueChange, options }: { label: string; value: string; onValueChange: (value: string) => void; options: Array<[string, string]> }) {
  return (
    <div className="grid gap-2">
      <Label>{label}</Label>
      <Select value={value} onValueChange={onValueChange}>
        <SelectTrigger><SelectValue /></SelectTrigger>
        <SelectContent>
          {options.map(([optionValue, labelText]) => <SelectItem key={optionValue} value={optionValue}>{labelText}</SelectItem>)}
        </SelectContent>
      </Select>
    </div>
  )
}

function addRange(children: Array<{ field: string; op: string; value: unknown }>, field: string, min: string, max: string, defaultMin: number, defaultMax: number) {
  if (min || max) {
    children.push({ field, op: "between", value: [min ? Number(min) : defaultMin, max ? Number(max) : defaultMax] })
  }
}

function normalizeItem(item: ScreeningRunItem) {
  return { ...item, code: item.symbol || item.code, name: item.name || item.symbol || item.code, market: item.market || "A股" }
}

function formatMarketCap(value?: number) {
  if (value == null) return "-"
  if (value >= 10000) return `${(value / 10000).toFixed(2)} 亿`
  return `${value.toFixed(2)} 万`
}
