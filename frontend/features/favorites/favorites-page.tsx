"use client"

import Link from "next/link"
import { useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Plus, RefreshCw } from "lucide-react"
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
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { favoritesApi, type FavoriteItem } from "@/libs/api/favorites"
import { formatDateTime } from "@/libs/utils/datetime"

function unwrap<T>(response: { data: T }) {
  return response.data
}

function symbolOf(item: FavoriteItem) {
  return item.symbol || item.stock_code || ""
}

export function FavoritesPage() {
  const queryClient = useQueryClient()
  const [keyword, setKeyword] = useState("")
  const [open, setOpen] = useState(false)
  const [removeTarget, setRemoveTarget] = useState<FavoriteItem | null>(null)
  const [form, setForm] = useState({ symbol: "", stock_name: "", market: "A股", tags: "", notes: "" })
  const listQuery = useQuery({ queryKey: ["favorites", "list"], queryFn: () => favoritesApi.list().then(unwrap), retry: false })
  const tagsQuery = useQuery({ queryKey: ["favorites", "tags"], queryFn: () => favoritesApi.tags().then(unwrap), retry: false })

  const addMutation = useMutation({
    mutationFn: () => favoritesApi.add({ ...form, tags: form.tags.split(",").map((item) => item.trim()).filter(Boolean) }),
    onSuccess: () => {
      toast.success("自选股已添加")
      setOpen(false)
      setForm({ symbol: "", stock_name: "", market: "A股", tags: "", notes: "" })
      void queryClient.invalidateQueries({ queryKey: ["favorites"] })
    },
    onError: (error) => toast.error(error.message)
  })
  const removeMutation = useMutation({
    mutationFn: (symbol: string) => favoritesApi.remove(symbol),
    onSuccess: () => {
      toast.success("自选股已移除")
      void queryClient.invalidateQueries({ queryKey: ["favorites"] })
    },
    onError: (error) => toast.error(error.message)
  })
  const syncMutation = useMutation({
    mutationFn: () => favoritesApi.syncRealtime().then(unwrap),
    onSuccess: (data) => {
      toast.success(data.message || `同步完成：${data.success_count}/${data.total}`)
      void queryClient.invalidateQueries({ queryKey: ["favorites"] })
    },
    onError: (error) => toast.error(error.message)
  })

  const favorites = (listQuery.data || []).filter((item) => {
    const text = `${symbolOf(item)} ${item.stock_name} ${(item.tags || []).join(" ")}`.toLowerCase()
    return text.includes(keyword.toLowerCase())
  })

  return (
    <div>
      <PageHeader
        title="我的自选股"
        description="管理关注股票、标签、备注和实时行情同步。"
        actions={
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => syncMutation.mutate()} disabled={syncMutation.isPending}><RefreshCw className="mr-2 size-4" />同步实时行情</Button>
            <Button onClick={() => setOpen(true)}><Plus className="mr-2 size-4" />添加自选股</Button>
          </div>
        }
      />
      <Card>
        <CardHeader><CardTitle>筛选</CardTitle></CardHeader>
        <CardContent className="grid gap-4 md:grid-cols-3">
          <Input placeholder="搜索股票代码、名称或标签" value={keyword} onChange={(event) => setKeyword(event.target.value)} />
          <div className="flex flex-wrap gap-2">
            {(tagsQuery.data || []).map((tag) => <Badge key={tag} variant="secondary">{tag}</Badge>)}
          </div>
        </CardContent>
      </Card>
      <Card className="mt-6">
        <CardHeader><CardTitle>自选股列表</CardTitle></CardHeader>
        <CardContent>
          {!favorites.length ? <EmptyState title="暂无自选股" /> : (
            <div className="overflow-x-auto rounded-md border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>股票</TableHead>
                    <TableHead>市场</TableHead>
                    <TableHead>价格</TableHead>
                    <TableHead>涨跌幅</TableHead>
                    <TableHead>标签</TableHead>
                    <TableHead>添加时间</TableHead>
                    <TableHead>操作</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {favorites.map((item) => (
                    <TableRow key={symbolOf(item)}>
                      <TableCell><Link className="text-primary hover:underline" href={`/stocks/${symbolOf(item)}`}>{symbolOf(item)} · {item.stock_name}</Link></TableCell>
                      <TableCell>{item.market || "A股"}</TableCell>
                      <TableCell>{item.current_price?.toFixed(2) || "-"}</TableCell>
                      <TableCell>{item.change_percent?.toFixed(2) || "-"}%</TableCell>
                      <TableCell>{(item.tags || []).map((tag) => <Badge key={tag} className="mr-1" variant="secondary">{tag}</Badge>)}</TableCell>
                      <TableCell>{item.added_at ? formatDateTime(item.added_at) : "-"}</TableCell>
                      <TableCell>
                        <div className="flex gap-2">
                          <Button size="sm" variant="outline" asChild><Link href={`/analysis/single?symbol=${symbolOf(item)}`}>分析</Link></Button>
                          <Button size="sm" variant="destructive" onClick={() => setRemoveTarget(item)}>移除</Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>添加自选股</DialogTitle>
            <DialogDescription>输入股票代码、名称、市场、标签和备注。</DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="grid gap-2"><Label>股票代码</Label><Input value={form.symbol} onChange={(event) => setForm((value) => ({ ...value, symbol: event.target.value }))} /></div>
            <div className="grid gap-2"><Label>股票名称</Label><Input value={form.stock_name} onChange={(event) => setForm((value) => ({ ...value, stock_name: event.target.value }))} /></div>
            <div className="grid gap-2"><Label>市场</Label><Input value={form.market} onChange={(event) => setForm((value) => ({ ...value, market: event.target.value }))} /></div>
            <div className="grid gap-2"><Label>标签</Label><Input placeholder="逗号分隔" value={form.tags} onChange={(event) => setForm((value) => ({ ...value, tags: event.target.value }))} /></div>
            <div className="grid gap-2"><Label>备注</Label><Input value={form.notes} onChange={(event) => setForm((value) => ({ ...value, notes: event.target.value }))} /></div>
            <Button onClick={() => addMutation.mutate()} disabled={addMutation.isPending}>添加</Button>
          </div>
        </DialogContent>
      </Dialog>
      <ConfirmDialog
        open={Boolean(removeTarget)}
        title="移除自选股"
        description={`确定要移除 ${removeTarget ? removeTarget.stock_name || symbolOf(removeTarget) : ""} 吗？`}
        confirmText="移除"
        destructive
        onOpenChange={(nextOpen) => {
          if (!nextOpen) setRemoveTarget(null)
        }}
        onConfirm={() => {
          const symbol = removeTarget ? symbolOf(removeTarget) : ""
          if (symbol) removeMutation.mutate(symbol)
          setRemoveTarget(null)
        }}
      />
    </div>
  )
}
