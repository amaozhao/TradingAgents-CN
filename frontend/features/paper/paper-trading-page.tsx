"use client"

import Link from "next/link"
import { useRouter, useSearchParams } from "next/navigation"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Plus, RefreshCw } from "lucide-react"
import { useState } from "react"
import { toast } from "sonner"

import { ConfirmDialog } from "@/components/feedback/confirm-dialog"
import { EmptyState } from "@/components/feedback/empty-state"
import { PageHeader } from "@/components/feedback/page-header"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { paperApi, type CurrencyAmount, type PaperPositionItem, type PlaceOrderPayload } from "@/libs/api/paper"
import { formatDateTime } from "@/libs/utils/datetime"

type MarketCode = "CN" | "HK" | "US"

const marketTabs: Array<{ value: MarketCode; label: string; currency: keyof CurrencyAmount; symbol: string; analysisMarket: string }> = [
  { value: "CN", label: "A股", currency: "CNY", symbol: "¥", analysisMarket: "A股" },
  { value: "HK", label: "港股", currency: "HKD", symbol: "HK$", analysisMarket: "港股" },
  { value: "US", label: "美股", currency: "USD", symbol: "$", analysisMarket: "美股" }
]

function unwrap<T>(response: T | { data: T } | { success?: boolean; data: T }) {
  if (response && typeof response === "object" && "data" in response) {
    return response.data as T
  }
  return response as T
}

function amount(value: CurrencyAmount | number | undefined, currency: keyof CurrencyAmount) {
  if (typeof value === "number") return currency === "CNY" ? value : 0
  return value?.[currency] || 0
}

function fmt(value?: number | null) {
  return typeof value === "number" && Number.isFinite(value) ? value.toFixed(2) : "-"
}

function marketOf(code?: string): MarketCode {
  const value = String(code || "").trim().toUpperCase()
  if (/^[A-Z]+$/.test(value)) return "US"
  if (value.endsWith(".HK") || /^\d{4,5}$/.test(value)) return "HK"
  return "CN"
}

function currencySymbol(currency?: string) {
  if (currency === "HKD") return "HK$"
  if (currency === "USD") return "$"
  return "¥"
}

export function PaperTradingPage() {
  const router = useRouter()
  const params = useSearchParams()
  const queryClient = useQueryClient()
  const initialCode = params.get("code") || ""
  const initialSide = params.get("side") === "sell" ? "sell" : "buy"
  const initialQuantity = Number(params.get("quantity") || params.get("qty") || 100)
  const initialAnalysisId = params.get("analysis_id") || undefined
  const [activeMarket, setActiveMarket] = useState<MarketCode>(marketOf(initialCode))
  const [orderOpen, setOrderOpen] = useState(Boolean(initialCode || initialAnalysisId))
  const [resetOpen, setResetOpen] = useState(false)
  const [sellTarget, setSellTarget] = useState<PaperPositionItem | null>(null)
  const [order, setOrder] = useState<PlaceOrderPayload>({
    code: initialCode,
    side: initialSide as "buy" | "sell",
    quantity: Number.isFinite(initialQuantity) && initialQuantity > 0 ? Math.round(initialQuantity) : 100,
    analysis_id: initialAnalysisId
  })

  const accountQuery = useQuery({ queryKey: ["paper", "account"], queryFn: () => paperApi.getAccount().then(unwrap), retry: false })
  const positionsQuery = useQuery({ queryKey: ["paper", "positions"], queryFn: () => paperApi.getPositions().then(unwrap), retry: false })
  const ordersQuery = useQuery({ queryKey: ["paper", "orders"], queryFn: () => paperApi.getOrders().then(unwrap), retry: false })

  const refreshAll = () => {
    void queryClient.invalidateQueries({ queryKey: ["paper"] })
  }

  const placeOrderMutation = useMutation({
    mutationFn: (payload: PlaceOrderPayload) => paperApi.placeOrder(payload).then(unwrap),
    onSuccess: () => {
      toast.success("模拟订单已提交")
      setOrderOpen(false)
      setSellTarget(null)
      refreshAll()
    },
    onError: (error) => toast.error(error.message)
  })
  const resetMutation = useMutation({
    mutationFn: () => paperApi.resetAccount(),
    onSuccess: () => {
      toast.success("模拟账户已重置")
      refreshAll()
    },
    onError: (error) => toast.error(error.message)
  })

  const account = accountQuery.data?.account
  const allPositions = positionsQuery.data?.items || accountQuery.data?.positions || []
  const allOrders = ordersQuery.data?.items || []
  const positions = allPositions.filter((item) => (item.market || marketOf(item.code)) === activeMarket)
  const orders = allOrders.filter((item) => (item.market || marketOf(item.code)) === activeMarket)
  const activeMeta = marketTabs.find((item) => item.value === activeMarket) || marketTabs[0]

  const submitSellTarget = () => {
    if (!sellTarget) return
    placeOrderMutation.mutate({ side: "sell", code: sellTarget.code, quantity: sellTarget.quantity })
  }

  const goAnalysisWithCode = (code: string) => {
    const market = marketTabs.find((item) => item.value === marketOf(code))?.analysisMarket || "A股"
    router.push(`/analysis/single?stock=${encodeURIComponent(code)}&market=${encodeURIComponent(market)}`)
  }

  return (
    <div>
      <PageHeader
        title="模拟交易"
        description="使用虚拟资金练习下单、查看持仓和订单记录。"
        actions={
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" onClick={refreshAll}><RefreshCw className="mr-2 size-4" />刷新</Button>
            <Button onClick={() => setOrderOpen(true)}><Plus className="mr-2 size-4" />下市场单</Button>
            <Button variant="destructive" onClick={() => setResetOpen(true)}>重置账户</Button>
          </div>
        }
      />
      <Card>
        <CardContent className="space-y-2 p-4 text-sm text-muted-foreground">
          <p><strong className="text-foreground">模拟性质：</strong>本功能使用虚拟资金，不涉及真实资金交易，仅供学习和练习使用。</p>
          <p><strong className="text-foreground">数据延迟：</strong>行情、成交价格和成交时机仅供参考，不应作为实盘投资决策依据。</p>
        </CardContent>
      </Card>

      <Tabs className="mt-6" value={activeMarket} onValueChange={(value) => setActiveMarket(value as MarketCode)}>
        <TabsList>
          {marketTabs.map((item) => <TabsTrigger key={item.value} value={item.value}>{item.label}</TabsTrigger>)}
        </TabsList>
        {marketTabs.map((market) => (
          <TabsContent key={market.value} value={market.value} className="mt-4">
            <div className="grid gap-4 md:grid-cols-4">
              <Card><CardContent className="p-5"><div className="text-sm text-muted-foreground">可用资金</div><div className="mt-2 text-2xl font-semibold">{market.symbol}{fmt(amount(account?.cash, market.currency))}</div></CardContent></Card>
              <Card><CardContent className="p-5"><div className="text-sm text-muted-foreground">持仓市值</div><div className="mt-2 text-2xl font-semibold">{market.symbol}{fmt(amount(account?.positions_value, market.currency))}</div></CardContent></Card>
              <Card><CardContent className="p-5"><div className="text-sm text-muted-foreground">总资产</div><div className="mt-2 text-2xl font-semibold">{market.symbol}{fmt(amount(account?.equity, market.currency))}</div></CardContent></Card>
              <Card><CardContent className="p-5"><div className="text-sm text-muted-foreground">已实现盈亏</div><div className="mt-2 text-2xl font-semibold">{market.symbol}{fmt(amount(account?.realized_pnl, market.currency))}</div></CardContent></Card>
            </div>
          </TabsContent>
        ))}
      </Tabs>

      <div className="mt-6 grid gap-6 xl:grid-cols-2">
        <Card>
          <CardHeader><CardTitle>持仓 ({positions.length})</CardTitle></CardHeader>
          <CardContent>
            {!positions.length ? <EmptyState title="暂无持仓" /> : (
              <Table>
                <TableHeader><TableRow><TableHead>代码</TableHead><TableHead>名称</TableHead><TableHead>数量</TableHead><TableHead>均价</TableHead><TableHead>最新价</TableHead><TableHead>浮盈亏</TableHead><TableHead>操作</TableHead></TableRow></TableHeader>
                <TableBody>
                  {positions.map((item) => {
                    const pnl = typeof item.unrealized_pnl === "number" ? item.unrealized_pnl : (Number(item.last_price || 0) - Number(item.avg_cost || 0)) * Number(item.quantity || 0)
                    return (
                      <TableRow key={item.code}>
                        <TableCell><Link className="text-primary hover:underline" href={`/stocks/${item.code}`}>{item.code}</Link></TableCell>
                        <TableCell>{item.name || "-"}</TableCell>
                        <TableCell>{item.quantity}{typeof item.available_qty === "number" && item.available_qty < item.quantity ? <span className="ml-1 text-xs text-muted-foreground">(可用{item.available_qty})</span> : null}</TableCell>
                        <TableCell>{currencySymbol(item.currency)}{fmt(item.avg_cost)}</TableCell>
                        <TableCell>{currencySymbol(item.currency)}{fmt(item.last_price)}</TableCell>
                        <TableCell className={pnl >= 0 ? "text-emerald-600" : "text-destructive"}>{currencySymbol(item.currency)}{fmt(pnl)}</TableCell>
                        <TableCell>
                          <div className="flex flex-wrap gap-2">
                            <Button size="sm" variant="outline" asChild><Link href={`/stocks/${item.code}`}>详情</Link></Button>
                            <Button size="sm" variant="outline" aria-label={`分析 ${item.code}`} onClick={() => goAnalysisWithCode(item.code)}>分析</Button>
                            <Button size="sm" variant="destructive" aria-label={`卖出 ${item.code}`} onClick={() => setSellTarget(item)}>卖出</Button>
                          </div>
                        </TableCell>
                      </TableRow>
                    )
                  })}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle>订单记录 ({orders.length})</CardTitle></CardHeader>
          <CardContent>
            {!orders.length ? <EmptyState title="暂无订单" /> : (
              <Table>
                <TableHeader><TableRow><TableHead>时间</TableHead><TableHead>方向</TableHead><TableHead>代码</TableHead><TableHead>名称</TableHead><TableHead>价格</TableHead><TableHead>数量</TableHead><TableHead>状态</TableHead><TableHead>关联分析</TableHead></TableRow></TableHeader>
                <TableBody>
                  {orders.map((item) => (
                    <TableRow key={`${item.code}-${item.created_at}-${item.side}`}>
                      <TableCell>{formatDateTime(item.created_at)}</TableCell>
                      <TableCell><Badge variant={item.side === "buy" ? "default" : "destructive"}>{item.side === "buy" ? "买入" : "卖出"}</Badge></TableCell>
                      <TableCell><Link className="text-primary hover:underline" href={`/stocks/${item.code}`}>{item.code}</Link></TableCell>
                      <TableCell>{item.name || "-"}</TableCell>
                      <TableCell>{fmt(item.price)}</TableCell>
                      <TableCell>{item.quantity}</TableCell>
                      <TableCell>{item.status === "filled" ? "已成交" : item.status}</TableCell>
                      <TableCell>{item.analysis_id ? <Button size="sm" variant="outline" asChild><Link href={`/reports/view/${item.analysis_id}`}>查看报告</Link></Button> : "-"}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
      </div>

      <Dialog open={orderOpen} onOpenChange={setOrderOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>下市场单</DialogTitle>
            <DialogDescription>提交模拟交易买入或卖出订单。</DialogDescription>
          </DialogHeader>
          {order.analysis_id ? (
            <div className="rounded-md border bg-muted/40 p-3 text-sm">
              来自分析报告：{order.analysis_id}
              <Button className="ml-2" size="sm" variant="link" asChild><Link href={`/reports/view/${order.analysis_id}`}>查看报告</Link></Button>
            </div>
          ) : null}
          <div className="space-y-4">
            <div className="grid gap-2">
              <Label htmlFor="paper-order-side">方向</Label>
              <Select value={order.side} onValueChange={(value: "buy" | "sell") => setOrder((next) => ({ ...next, side: value }))}>
                <SelectTrigger id="paper-order-side"><SelectValue /></SelectTrigger>
                <SelectContent><SelectItem value="buy">买入</SelectItem><SelectItem value="sell">卖出</SelectItem></SelectContent>
              </Select>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="paper-order-code">代码</Label>
              <Input id="paper-order-code" value={order.code} onChange={(event) => setOrder((next) => ({ ...next, code: event.target.value }))} placeholder="A股: 600519 | 港股: 0700 | 美股: AAPL" />
            </div>
            <div className="grid gap-2 text-sm text-muted-foreground">
              <Label>市场</Label>
              <Badge variant="secondary">{marketTabs.find((item) => item.value === marketOf(order.code))?.label || activeMeta.label}</Badge>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="paper-order-quantity">数量</Label>
              <Input id="paper-order-quantity" type="number" min={1} value={order.quantity} onChange={(event) => setOrder((next) => ({ ...next, quantity: Number(event.target.value) || 1 }))} />
            </div>
            <Button onClick={() => placeOrderMutation.mutate(order)} disabled={placeOrderMutation.isPending || !order.code}>提交</Button>
          </div>
        </DialogContent>
      </Dialog>
      <ConfirmDialog
        open={resetOpen}
        title="重置模拟账户"
        description="确定要重置模拟账户吗？持仓和订单状态会被重置。"
        confirmText="重置"
        destructive
        onOpenChange={setResetOpen}
        onConfirm={() => {
          resetMutation.mutate()
          setResetOpen(false)
        }}
      />
      <ConfirmDialog
        open={Boolean(sellTarget)}
        title="卖出确认"
        description={`确认卖出 ${sellTarget?.name || sellTarget?.code || ""}？当前持仓：${sellTarget?.quantity || 0} 股。`}
        confirmText="确认卖出"
        destructive
        onOpenChange={(nextOpen) => {
          if (!nextOpen) setSellTarget(null)
        }}
        onConfirm={submitSellTarget}
      />
    </div>
  )
}
