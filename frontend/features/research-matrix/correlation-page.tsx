"use client"

import { Send } from "lucide-react"

import { PageHeader } from "@/components/feedback/page-header"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { CorrelationHeatmap } from "@/features/research-matrix/correlation-heatmap"

export function CorrelationPage() {
  return (
    <div>
      <PageHeader
        title="相关性矩阵"
        description="对显式股票池、行业或用户宇宙执行私有相关性分析"
        actions={<Button variant="outline"><Send className="mr-2 size-4" />发送到 Agent</Button>}
      />
      <div className="grid gap-4 lg:grid-cols-[320px_minmax(0,1fr)_320px]">
        <section className="rounded-lg border bg-card p-4">
          <h2 className="mb-3 text-base font-semibold">Universe Selector</h2>
          <div className="grid gap-3">
            <Label>股票池</Label>
            <Input defaultValue="600519,000001,300750" />
            <Label>日期范围</Label>
            <div className="grid grid-cols-2 gap-2">
              <Input type="date" />
              <Input type="date" />
            </div>
            <Label>窗口</Label>
            <Input type="number" defaultValue={60} />
            <Label>方法</Label>
            <Select defaultValue="pearson">
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="pearson">Pearson</SelectItem>
                <SelectItem value="spearman">Spearman</SelectItem>
                <SelectItem value="kendall">Kendall</SelectItem>
              </SelectContent>
            </Select>
            <Button>计算矩阵</Button>
          </div>
        </section>
        <CorrelationHeatmap />
        <div className="space-y-4">
          <CandidateCard title="高相关组合" items={["600519 / 000001 · 0.62", "000001 / 300750 · 0.34"]} />
          <CandidateCard title="分散候选" items={["300750 · avg 0.26", "600519 · avg 0.40"]} />
        </div>
      </div>
    </div>
  )
}

function CandidateCard({ title, items }: { title: string; items: string[] }) {
  return (
    <Card>
      <CardHeader><CardTitle className="text-base">{title}</CardTitle></CardHeader>
      <CardContent>
        <ul className="space-y-2 text-sm">
          {items.map((item) => <li key={item} className="rounded-md border px-3 py-2">{item}</li>)}
        </ul>
      </CardContent>
    </Card>
  )
}
