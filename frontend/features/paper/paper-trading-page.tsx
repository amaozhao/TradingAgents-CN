"use client"

import Link from "next/link"
import { useSearchParams } from "next/navigation"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Plus } from "lucide-react"
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
import { paperApi, type CurrencyAmount } from "@/libs/api/paper"
import { formatDateTime } from "@/libs/utils/datetime"

function unwrap<T>(response: { data: T }) {
  return response.data
}

function amount(value: CurrencyAmount | number | undefined, currency: keyof CurrencyAmount) {
  if (typeof value === "number") return value
  return value?.[currency] || 0
}

function fmt(value?: number | null) {
  return typeof value === "number" && Number.isFinite(value) ? value.toFixed(2) : "-"
}

export function PaperTradingPage() {
  const params = useSearchParams()
  const queryClient = useQueryClient()
  const [orderOpen, setOrderOpen] = useState(Boolean(params.get("code")))
  const [resetOpen, setResetOpen] = useState(false)
  const [order, setOrder] = useState({ code: params.get("code") || "", side: "buy" as "buy" | "sell", quantity: 100 })
  const accountQuery = useQuery({ queryKey: ["paper", "account"], queryFn: () => paperApi.getAccount().then(unwrap), retry: false })
  const positionsQuery = useQuery({ queryKey: ["paper", "positions"], queryFn: () => paperApi.getPositions().then(unwrap), retry: false })
  const ordersQuery = useQuery({ queryKey: ["paper", "orders"], queryFn: () => paperApi.getOrders().then(unwrap), retry: false })
  const placeOrderMutation = useMutation({
    mutationFn: () => paperApi.placeOrder(order).then(unwrap),
    onSuccess: () => {
      toast.success("模拟订单已提交")
      setOrderOpen(false)
      void queryClient.invalidateQueries({ queryKey: ["paper"] })
    },
    onError: (error) => toast.error(error.message)
  })
  const resetMutation = useMutation({
    mutationFn: () => paperApi.resetAccount(),
    onSuccess: () => {
      toast.success("模拟账户已重置")
      void queryClient.invalidateQueries({ queryKey: ["paper"] })
    },
    onError: (error) => toast.error(error.message)
  })

  const account = accountQuery.data?.account
  const positions = positionsQuery.data?.items || accountQuery.data?.positions || []
  const orders = ordersQuery.data?.items || []

  return (
    <div>
      <PageHeader
        title="模拟交易"
        description="使用虚拟资金练习下单、查看持仓和订单记录。"
        actions={
          <div className="flex gap-2">
            <Button onClick={() => setOrderOpen(true)}><Plus className="mr-2 size-4" />下市场单</Button>
            <Button variant="destructive" onClick={() => setResetOpen(true)}>重置账户</Button>
          </div>
        }
      />
      <Card>
        <CardContent className="p-4 text-sm text-muted-foreground">
          模拟交易仅用于学习和练习，不涉及真实资金交易，成交价格和行情数据可能与实际市场存在差异。
        </CardContent>
      </Card>
      <div className="mt-6 grid gap-4 md:grid-cols-4">
        <Card><CardContent className="p-5"><div className="text-sm text-muted-foreground">A股现金</div><div className="mt-2 text-2xl font-semibold">¥{fmt(amount(account?.cash, "CNY"))}</div></CardContent></Card>
        <Card><CardContent className="p-5"><div className="text-sm text-muted-foreground">港股现金</div><div className="mt-2 text-2xl font-semibold">HK${fmt(amount(account?.cash, "HKD"))}</div></CardContent></Card>
        <Card><CardContent className="p-5"><div className="text-sm text-muted-foreground">美股现金</div><div className="mt-2 text-2xl font-semibold">${fmt(amount(account?.cash, "USD"))}</div></CardContent></Card>
        <Card><CardContent className="p-5"><div className="text-sm text-muted-foreground">更新时间</div><div className="mt-2 text-sm font-medium">{account?.updated_at ? formatDateTime(account.updated_at) : "-"}</div></CardContent></Card>
      </div>
      <div className="mt-6 grid gap-6 xl:grid-cols-2">
        <Card>
          <CardHeader><CardTitle>持仓</CardTitle></CardHeader>
          <CardContent>
            {!positions.length ? <EmptyState title="暂无持仓" /> : (
              <Table>
                <TableHeader><TableRow><TableHead>代码</TableHead><TableHead>数量</TableHead><TableHead>均价</TableHead><TableHead>最新价</TableHead><TableHead>浮盈亏</TableHead></TableRow></TableHeader>
                <TableBody>
                  {positions.map((item) => (
                    <TableRow key={item.code}>
                      <TableCell><Link className="text-primary hover:underline" href={`/stocks/${item.code}`}>{item.code}</Link></TableCell>
                      <TableCell>{item.quantity}</TableCell>
                      <TableCell>{fmt(item.avg_cost)}</TableCell>
                      <TableCell>{fmt(item.last_price)}</TableCell>
                      <TableCell>{fmt(item.unrealized_pnl)}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle>订单记录</CardTitle></CardHeader>
          <CardContent>
            {!orders.length ? <EmptyState title="暂无订单" /> : (
              <Table>
                <TableHeader><TableRow><TableHead>时间</TableHead><TableHead>方向</TableHead><TableHead>代码</TableHead><TableHead>价格</TableHead><TableHead>数量</TableHead><TableHead>状态</TableHead></TableRow></TableHeader>
                <TableBody>
                  {orders.map((item) => (
                    <TableRow key={`${item.code}-${item.created_at}-${item.side}`}>
                      <TableCell>{formatDateTime(item.created_at)}</TableCell>
                      <TableCell><Badge variant={item.side === "buy" ? "default" : "destructive"}>{item.side === "buy" ? "买入" : "卖出"}</Badge></TableCell>
                      <TableCell>{item.code}</TableCell>
                      <TableCell>{fmt(item.price)}</TableCell>
                      <TableCell>{item.quantity}</TableCell>
                      <TableCell>{item.status}</TableCell>
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
          <div className="space-y-4">
            <div className="grid gap-2"><Label>方向</Label><Select value={order.side} onValueChange={(value: "buy" | "sell") => setOrder((next) => ({ ...next, side: value }))}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent><SelectItem value="buy">买入</SelectItem><SelectItem value="sell">卖出</SelectItem></SelectContent></Select></div>
            <div className="grid gap-2"><Label>代码</Label><Input value={order.code} onChange={(event) => setOrder((next) => ({ ...next, code: event.target.value }))} /></div>
            <div className="grid gap-2"><Label>数量</Label><Input type="number" min={1} value={order.quantity} onChange={(event) => setOrder((next) => ({ ...next, quantity: Number(event.target.value) || 1 }))} /></div>
            <Button onClick={() => placeOrderMutation.mutate()} disabled={placeOrderMutation.isPending || !order.code}>提交</Button>
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
    </div>
  )
}
