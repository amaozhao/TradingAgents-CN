"use client"

import Link from "next/link"
import { useRouter } from "next/navigation"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import type { EChartsOption } from "echarts"
import { CreditCard, RefreshCw, Star } from "lucide-react"
import { toast } from "sonner"

import { EChartPanel } from "@/components/charts/e-chart-panel"
import { EmptyState } from "@/components/feedback/empty-state"
import { PageHeader } from "@/components/feedback/page-header"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { favoritesApi } from "@/libs/api/favorites"
import { stocksApi, type KlineBar } from "@/libs/api/stocks"
import { formatDateTime } from "@/libs/utils/datetime"

function unwrap<T>(response: { data: T }) {
  return response.data
}

function fmtNumber(value?: number | null, digits = 2) {
  return typeof value === "number" && Number.isFinite(value) ? value.toFixed(digits) : "-"
}

function fmtAmount(value?: number | null) {
  if (typeof value !== "number" || !Number.isFinite(value)) return "-"
  if (Math.abs(value) >= 100000000) return `${(value / 100000000).toFixed(2)} 亿`
  if (Math.abs(value) >= 10000) return `${(value / 10000).toFixed(2)} 万`
  return value.toFixed(2)
}

function buildKlineOption(items: KlineBar[]): EChartsOption {
  return {
    tooltip: { trigger: "axis" },
    xAxis: { type: "category", data: items.map((item) => item.time) },
    yAxis: { type: "value", scale: true },
    series: [
      {
        type: "candlestick",
        data: items.map((item) => [item.open ?? 0, item.close ?? 0, item.low ?? 0, item.high ?? 0])
      }
    ]
  }
}

export function StockDetailPage({ code }: { code: string }) {
  const router = useRouter()
  const queryClient = useQueryClient()
  const quoteQuery = useQuery({ queryKey: ["stocks", code, "quote"], queryFn: () => stocksApi.getQuote(code).then(unwrap), retry: false })
  const fundamentalsQuery = useQuery({ queryKey: ["stocks", code, "fundamentals"], queryFn: () => stocksApi.getFundamentals(code).then(unwrap), retry: false })
  const klineQuery = useQuery({ queryKey: ["stocks", code, "kline"], queryFn: () => stocksApi.getKline(code).then(unwrap), retry: false })
  const newsQuery = useQuery({ queryKey: ["stocks", code, "news"], queryFn: () => stocksApi.getNews(code, 30, 20, true).then(unwrap), retry: false })
  const favoriteQuery = useQuery({ queryKey: ["favorites", "check", code], queryFn: () => favoritesApi.check(code).then(unwrap), retry: false })

  const toggleFavoriteMutation = useMutation({
    mutationFn: async () => {
      if (favoriteQuery.data?.is_favorite) {
        await favoritesApi.remove(code)
      } else {
        await favoritesApi.add({
          symbol: code,
          stock_name: quoteQuery.data?.name || fundamentalsQuery.data?.name || code,
          market: quoteQuery.data?.market || fundamentalsQuery.data?.market || "A股"
        })
      }
    },
    onSuccess: () => {
      toast.success("自选股已更新")
      void queryClient.invalidateQueries({ queryKey: ["favorites"] })
    },
    onError: (error) => toast.error(error.message)
  })

  const quote = quoteQuery.data
  const fundamentals = fundamentalsQuery.data
  const klineItems = klineQuery.data?.items || []
  const news = newsQuery.data?.items || []
  const isFavorite = Boolean(favoriteQuery.data?.is_favorite)
  const change = quote?.change_percent ?? 0

  return (
    <div>
      <PageHeader
        title={`${quote?.name || fundamentals?.name || code}`}
        description={`${code} · ${quote?.market || fundamentals?.market || "-"} · ${quote?.updated_at ? `更新于 ${formatDateTime(quote.updated_at)}` : "股票详情"}`}
        actions={
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" onClick={() => toggleFavoriteMutation.mutate()}>
              <Star className="mr-2 size-4" />{isFavorite ? "移出自选" : "加入自选"}
            </Button>
            <Button variant="outline" onClick={() => router.push(`/analysis/single?symbol=${code}`)}>
              <RefreshCw className="mr-2 size-4" />发起分析
            </Button>
            <Button onClick={() => router.push(`/paper?code=${code}`)}>
              <CreditCard className="mr-2 size-4" />模拟交易
            </Button>
          </div>
        }
      />
      <div className="grid gap-4 md:grid-cols-4">
        <Card className="md:col-span-2">
          <CardContent className="p-5">
            <div className={change >= 0 ? "text-3xl font-semibold text-emerald-600" : "text-3xl font-semibold text-destructive"}>
              {fmtNumber(quote?.price)}
            </div>
            <div className="mt-2 text-sm text-muted-foreground">涨跌幅 {fmtNumber(change)}%</div>
          </CardContent>
        </Card>
        <Card><CardContent className="p-5"><div className="text-sm text-muted-foreground">成交额</div><div className="mt-2 text-xl font-semibold">{fmtAmount(quote?.amount)}</div></CardContent></Card>
        <Card><CardContent className="p-5"><div className="text-sm text-muted-foreground">换手率</div><div className="mt-2 text-xl font-semibold">{fmtNumber(quote?.turnover_rate)}%</div></CardContent></Card>
      </div>
      <div className="mt-6 grid gap-6 xl:grid-cols-[minmax(0,1fr)_360px]">
        <div className="space-y-6">
          <Card>
            <CardHeader><CardTitle>价格K线</CardTitle></CardHeader>
            <CardContent>
              <EChartPanel option={buildKlineOption(klineItems)} empty={!klineItems.length} height={360} />
            </CardContent>
          </Card>
          <Card>
            <CardHeader><CardTitle>近期新闻与公告</CardTitle></CardHeader>
            <CardContent>
              {!news.length ? <EmptyState title="暂无新闻" /> : (
                <div className="space-y-3">
                  {news.map((item) => (
                    <div key={`${item.title}-${item.time}`} className="rounded-md border p-3">
                      <div className="flex items-center gap-2">
                        <Badge variant={item.type === "announcement" ? "secondary" : "default"}>{item.type === "announcement" ? "公告" : "新闻"}</Badge>
                        {item.url && item.url !== "#" ? <a className="font-medium hover:underline" href={item.url} target="_blank" rel="noreferrer">{item.title}</a> : <span className="font-medium">{item.title}</span>}
                      </div>
                      <div className="mt-2 text-xs text-muted-foreground">{item.source} · {item.time}</div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </div>
        <div className="space-y-6">
          <Card>
            <CardHeader><CardTitle>基本面快照</CardTitle></CardHeader>
            <CardContent>
              <Table>
                <TableBody>
                  <TableRow><TableCell>行业</TableCell><TableCell>{fundamentals?.industry || "-"}</TableCell></TableRow>
                  <TableRow><TableCell>板块</TableCell><TableCell>{fundamentals?.sector || "-"}</TableCell></TableRow>
                  <TableRow><TableCell>总市值</TableCell><TableCell>{fmtAmount(fundamentals?.total_mv)}</TableCell></TableRow>
                  <TableRow><TableCell>PE(TTM)</TableCell><TableCell>{fmtNumber(fundamentals?.pe_ttm ?? fundamentals?.pe)}</TableCell></TableRow>
                  <TableRow><TableCell>PB</TableCell><TableCell>{fmtNumber(fundamentals?.pb_mrq ?? fundamentals?.pb)}</TableCell></TableRow>
                  <TableRow><TableCell>ROE</TableCell><TableCell>{fmtNumber(fundamentals?.roe)}%</TableCell></TableRow>
                </TableBody>
              </Table>
            </CardContent>
          </Card>
          <Card>
            <CardHeader><CardTitle>行情指标</CardTitle></CardHeader>
            <CardContent>
              <Table>
                <TableHeader><TableRow><TableHead>指标</TableHead><TableHead>值</TableHead></TableRow></TableHeader>
                <TableBody>
                  <TableRow><TableCell>昨收</TableCell><TableCell>{fmtNumber(quote?.prev_close)}</TableCell></TableRow>
                  <TableRow><TableCell>振幅</TableCell><TableCell>{fmtNumber(quote?.amplitude)}%</TableCell></TableRow>
                  <TableRow><TableCell>交易日期</TableCell><TableCell>{quote?.trade_date || "-"}</TableCell></TableRow>
                </TableBody>
              </Table>
            </CardContent>
          </Card>
          <Link className="block rounded-md border p-4 text-sm hover:bg-muted" href={`/analysis/single?symbol=${code}`}>进入单股分析</Link>
        </div>
      </div>
    </div>
  )
}
