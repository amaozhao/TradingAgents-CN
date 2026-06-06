"use client"

import Link from "next/link"
import { useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Database, Plus, RefreshCw } from "lucide-react"
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
import { stockSyncApi } from "@/libs/api/stock-sync"
import { tagsApi } from "@/libs/api/tags"
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
  const [batchSyncOpen, setBatchSyncOpen] = useState(false)
  const [tagDialogOpen, setTagDialogOpen] = useState(false)
  const [removeTarget, setRemoveTarget] = useState<FavoriteItem | null>(null)
  const [form, setForm] = useState({ symbol: "", stock_name: "", market: "A股", tags: "", notes: "" })
  const [newTagName, setNewTagName] = useState("")
  const [selectedSymbols, setSelectedSymbols] = useState<string[]>([])
  const [batchSyncForm, setBatchSyncForm] = useState({
    syncHistorical: true,
    syncFinancial: false,
    syncBasic: false,
    dataSource: "tushare" as "tushare" | "akshare",
    days: 365
  })
  const listQuery = useQuery({ queryKey: ["favorites", "list"], queryFn: () => favoritesApi.list().then(unwrap), retry: false })
  const tagsQuery = useQuery({ queryKey: ["favorites", "tags"], queryFn: () => favoritesApi.tags().then(unwrap), retry: false })
  const tagItemsQuery = useQuery({ queryKey: ["tags", "list"], queryFn: () => tagsApi.list().then(unwrap), retry: false })

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
  const batchSyncMutation = useMutation({
    mutationFn: () => stockSyncApi.syncBatch({
      symbols: selectedSymbols,
      sync_historical: batchSyncForm.syncHistorical,
      sync_financial: batchSyncForm.syncFinancial,
      sync_basic: batchSyncForm.syncBasic,
      data_source: batchSyncForm.dataSource,
      days: batchSyncForm.days
    }),
    onSuccess: (response) => {
      const data = response.data
      toast.success(`批量同步完成：${data.total} 只股票`)
      setBatchSyncOpen(false)
      setSelectedSymbols([])
      void queryClient.invalidateQueries({ queryKey: ["favorites"] })
    },
    onError: (error) => toast.error(error.message)
  })
  const createTagMutation = useMutation({
    mutationFn: (name: string) => tagsApi.create({ name }),
    onSuccess: () => {
      toast.success("标签已添加")
      setNewTagName("")
      void queryClient.invalidateQueries({ queryKey: ["tags"] })
      void queryClient.invalidateQueries({ queryKey: ["favorites", "tags"] })
    },
    onError: (error) => toast.error(error.message)
  })
  const removeTagMutation = useMutation({
    mutationFn: (id: string) => tagsApi.remove(id),
    onSuccess: () => {
      toast.success("标签已删除")
      void queryClient.invalidateQueries({ queryKey: ["tags"] })
      void queryClient.invalidateQueries({ queryKey: ["favorites"] })
    },
    onError: (error) => toast.error(error.message)
  })

  const favorites = (listQuery.data || []).filter((item) => {
    const text = `${symbolOf(item)} ${item.stock_name} ${(item.tags || []).join(" ")}`.toLowerCase()
    return text.includes(keyword.toLowerCase())
  })
  const selectedItems = favorites.filter((item) => selectedSymbols.includes(symbolOf(item)))
  const canBatchSync = selectedItems.length > 0 && selectedItems.every((item) => (item.market || "A股") === "A股")

  const toggleSelected = (symbol: string, checked: boolean) => {
    setSelectedSymbols((current) => {
      if (checked) return current.includes(symbol) ? current : [...current, symbol]
      return current.filter((item) => item !== symbol)
    })
  }

  return (
    <div>
      <PageHeader
        title="我的自选股"
        description="管理关注股票、标签、备注和实时行情同步。"
        actions={
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => setBatchSyncOpen(true)} disabled={!canBatchSync}>
              <Database className="mr-2 size-4" />
              批量同步数据 ({selectedSymbols.length})
            </Button>
            <Button variant="outline" onClick={() => setTagDialogOpen(true)}>标签管理</Button>
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
                    <TableHead className="w-10">
                      <span className="sr-only">选择</span>
                    </TableHead>
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
                      <TableCell>
                        <input
                          aria-label={`选择 ${symbolOf(item)}`}
                          type="checkbox"
                          checked={selectedSymbols.includes(symbolOf(item))}
                          onChange={(event) => toggleSelected(symbolOf(item), event.target.checked)}
                        />
                      </TableCell>
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
      <Dialog open={batchSyncOpen} onOpenChange={setBatchSyncOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>批量同步股票数据</DialogTitle>
            <DialogDescription>已选择 {selectedSymbols.length} 只 A 股，批量同步可能需要较长时间。</DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="grid gap-3">
              <Label>同步类型</Label>
              <label className="flex items-center gap-2 text-sm">
                <input type="checkbox" checked={batchSyncForm.syncHistorical} onChange={(event) => setBatchSyncForm((value) => ({ ...value, syncHistorical: event.target.checked }))} />
                历史行情
              </label>
              <label className="flex items-center gap-2 text-sm">
                <input type="checkbox" checked={batchSyncForm.syncFinancial} onChange={(event) => setBatchSyncForm((value) => ({ ...value, syncFinancial: event.target.checked }))} />
                财务数据
              </label>
              <label className="flex items-center gap-2 text-sm">
                <input type="checkbox" checked={batchSyncForm.syncBasic} onChange={(event) => setBatchSyncForm((value) => ({ ...value, syncBasic: event.target.checked }))} />
                基础资料
              </label>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="batch-sync-source">数据源</Label>
              <select
                id="batch-sync-source"
                className="h-9 rounded-md border bg-background px-3 text-sm"
                value={batchSyncForm.dataSource}
                onChange={(event) => setBatchSyncForm((value) => ({ ...value, dataSource: event.target.value as "tushare" | "akshare" }))}
              >
                <option value="tushare">Tushare</option>
                <option value="akshare">AKShare</option>
              </select>
            </div>
            {batchSyncForm.syncHistorical ? (
              <div className="grid gap-2">
                <Label htmlFor="batch-sync-days">历史数据天数</Label>
                <Input
                  id="batch-sync-days"
                  min={1}
                  max={3650}
                  type="number"
                  value={batchSyncForm.days}
                  onChange={(event) => setBatchSyncForm((value) => ({ ...value, days: Number(event.target.value) || 365 }))}
                />
              </div>
            ) : null}
            <Button
              onClick={() => batchSyncMutation.mutate()}
              disabled={batchSyncMutation.isPending || (!batchSyncForm.syncHistorical && !batchSyncForm.syncFinancial && !batchSyncForm.syncBasic)}
            >
              开始同步
            </Button>
          </div>
        </DialogContent>
      </Dialog>
      <Dialog open={tagDialogOpen} onOpenChange={setTagDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>标签管理</DialogTitle>
            <DialogDescription>维护自选股可用标签。</DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="flex gap-2">
              <div className="grid flex-1 gap-2">
                <Label htmlFor="new-tag-name">新标签名称</Label>
                <Input id="new-tag-name" value={newTagName} onChange={(event) => setNewTagName(event.target.value)} />
              </div>
              <Button className="self-end" onClick={() => createTagMutation.mutate(newTagName.trim())} disabled={!newTagName.trim() || createTagMutation.isPending}>
                添加标签
              </Button>
            </div>
            <div className="space-y-2 rounded-md border p-3">
              {(tagItemsQuery.data || []).length ? (tagItemsQuery.data || []).map((tag) => (
                <div key={tag.id} className="flex items-center justify-between gap-3 rounded-md border p-2">
                  <div>
                    <div className="font-medium">{tag.name}</div>
                    <div className="text-xs text-muted-foreground">排序 {tag.sort_order}</div>
                  </div>
                  <Button variant="outline" size="sm" onClick={() => removeTagMutation.mutate(tag.id)}>删除</Button>
                </div>
              )) : <EmptyState title="暂无标签" />}
            </div>
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
