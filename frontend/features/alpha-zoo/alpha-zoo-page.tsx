"use client"

import { Send } from "lucide-react"

import { PageHeader } from "@/components/feedback/page-header"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { AlphaBenchRunner } from "@/features/alpha-zoo/alpha-bench-runner"
import { AlphaFactorTable } from "@/features/alpha-zoo/alpha-factor-table"

export function AlphaZooPage() {
  return (
    <div>
      <PageHeader
        title="Alpha Zoo"
        description="浏览、筛选、基准测试和比较 Alpha 因子"
        actions={<Button variant="outline"><Send className="mr-2 size-4" />发送到 Agent</Button>}
      />
      <div className="grid gap-4 lg:grid-cols-[280px_minmax(0,1fr)_320px]">
        <section className="rounded-lg border bg-card p-4">
          <h2 className="mb-3 text-base font-semibold">因子筛选</h2>
          <div className="grid gap-3">
            <Label>Zoo</Label>
            <Select defaultValue="all">
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="all">全部</SelectItem>
                <SelectItem value="alpha101">Alpha101</SelectItem>
                <SelectItem value="gtja191">GTJA191</SelectItem>
                <SelectItem value="qlib158">Qlib158</SelectItem>
              </SelectContent>
            </Select>
            <Label>搜索</Label>
            <Input placeholder="因子 ID / 主题 / 字段" />
            <Label>Required Columns</Label>
            <Input defaultValue="open,high,low,close,volume,amount,vwap" />
          </div>
        </section>
        <AlphaFactorTable />
        <div className="space-y-4">
          <Card>
            <CardHeader><CardTitle className="text-base">因子详情</CardTitle></CardHeader>
            <CardContent className="space-y-2 text-sm">
              <p className="font-medium">alpha101_001</p>
              <p className="text-muted-foreground">公式、元数据、所需 panel 字段和运行状态。</p>
            </CardContent>
          </Card>
          <AlphaBenchRunner />
          <Card>
            <CardHeader><CardTitle className="text-base">IC/IR 摘要</CardTitle></CardHeader>
            <CardContent className="grid grid-cols-3 gap-2 text-sm">
              <Metric label="IC" value="0.041" />
              <Metric label="IR" value="0.62" />
              <Metric label="NAV" value="1.18" />
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border p-2">
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="font-semibold">{value}</div>
    </div>
  )
}
