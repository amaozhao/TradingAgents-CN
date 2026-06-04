"use client"

import Link from "next/link"
import { useMemo, useState } from "react"
import { useMutation, useQuery } from "@tanstack/react-query"
import { Search } from "lucide-react"
import { toast } from "sonner"

import { EmptyState } from "@/components/feedback/empty-state"
import { PageHeader } from "@/components/feedback/page-header"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { screeningApi, type ScreeningRunItem } from "@/libs/api/screening"
import { getCurrentDataSource } from "@/libs/api/sync"

function unwrap<T>(response: { data: T }) {
  return response.data
}

export function ScreeningPage() {
  const [industry, setIndustry] = useState("all")
  const [peMax, setPeMax] = useState("")
  const [pbMax, setPbMax] = useState("")
  const [changeMin, setChangeMin] = useState("")
  const [limit, setLimit] = useState("50")
  const [results, setResults] = useState<ScreeningRunItem[]>([])

  const currentSourceQuery = useQuery({ queryKey: ["sync", "current-source"], queryFn: () => getCurrentDataSource().then(unwrap), retry: false })
  const industriesQuery = useQuery({ queryKey: ["screening", "industries"], queryFn: () => screeningApi.getIndustries().then(unwrap), retry: false })

  const runMutation = useMutation({
    mutationFn: () => screeningApi.run({
      market: "CN",
      conditions: {
        industry: industry === "all" ? undefined : industry,
        pe_ttm: peMax ? { max: Number(peMax) } : undefined,
        pb_mrq: pbMax ? { max: Number(pbMax) } : undefined,
        pct_chg: changeMin ? { min: Number(changeMin) } : undefined
      },
      order_by: [{ field: "amount", direction: "desc" }],
      limit: Number(limit) || 50,
      offset: 0
    }).then(unwrap),
    onSuccess: (data) => {
      setResults(data.items)
      toast.success(`筛选完成：${data.total} 条结果`)
    },
    onError: (error) => toast.error(error.message)
  })

  const industries = industriesQuery.data?.industries || []
  const totalAmount = useMemo(() => results.reduce((sum, item) => sum + (item.amount || 0), 0), [results])

  return (
    <div>
      <PageHeader
        title="股票筛选"
        description={`通过多维度筛选条件查找股票。当前数据源：${currentSourceQuery.data?.name || "未知"}`}
        actions={<Button onClick={() => runMutation.mutate()} disabled={runMutation.isPending}><Search className="mr-2 size-4" />开始筛选</Button>}
      />
      <Card>
        <CardHeader><CardTitle>筛选条件</CardTitle></CardHeader>
        <CardContent className="grid gap-4 md:grid-cols-5">
          <div className="grid gap-2">
            <Label>行业分类</Label>
            <Select value={industry} onValueChange={setIndustry}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="all">全部行业</SelectItem>
                {industries.map((item) => <SelectItem key={item.value} value={item.value}>{item.label}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <div className="grid gap-2"><Label>PE 上限</Label><Input value={peMax} onChange={(event) => setPeMax(event.target.value)} type="number" /></div>
          <div className="grid gap-2"><Label>PB 上限</Label><Input value={pbMax} onChange={(event) => setPbMax(event.target.value)} type="number" /></div>
          <div className="grid gap-2"><Label>涨跌幅下限</Label><Input value={changeMin} onChange={(event) => setChangeMin(event.target.value)} type="number" /></div>
          <div className="grid gap-2"><Label>结果数量</Label><Input value={limit} onChange={(event) => setLimit(event.target.value)} type="number" min={1} max={500} /></div>
        </CardContent>
      </Card>
      <div className="mt-4 grid gap-4 md:grid-cols-3">
        <Card><CardContent className="p-5"><div className="text-sm text-muted-foreground">结果数</div><div className="mt-2 text-2xl font-semibold">{results.length}</div></CardContent></Card>
        <Card><CardContent className="p-5"><div className="text-sm text-muted-foreground">成交额合计</div><div className="mt-2 text-2xl font-semibold">{(totalAmount / 100000000).toFixed(2)} 亿</div></CardContent></Card>
        <Card><CardContent className="p-5"><div className="text-sm text-muted-foreground">排序</div><div className="mt-2 text-2xl font-semibold">成交额降序</div></CardContent></Card>
      </div>
      <Card className="mt-6">
        <CardHeader><CardTitle>筛选结果</CardTitle></CardHeader>
        <CardContent>
          {!results.length ? <EmptyState title="暂无筛选结果" /> : (
            <div className="overflow-x-auto rounded-md border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>股票代码</TableHead>
                    <TableHead>收盘价</TableHead>
                    <TableHead>涨跌幅</TableHead>
                    <TableHead>成交额</TableHead>
                    <TableHead>MA20</TableHead>
                    <TableHead>RSI14</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {results.map((item) => (
                    <TableRow key={item.code}>
                      <TableCell><Link className="text-primary hover:underline" href={`/stocks/${item.code}`}>{item.code}</Link></TableCell>
                      <TableCell>{item.close?.toFixed(2) || "-"}</TableCell>
                      <TableCell>{item.pct_chg?.toFixed(2) || "-"}%</TableCell>
                      <TableCell>{item.amount ? `${(item.amount / 100000000).toFixed(2)} 亿` : "-"}</TableCell>
                      <TableCell>{item.ma20?.toFixed(2) || "-"}</TableCell>
                      <TableCell>{item.rsi14?.toFixed(2) || "-"}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
