import Link from "next/link"
import { Cpu, FileText, Monitor, Search, Settings, Star, TrendingUp } from "lucide-react"

import { PageHeader } from "@/components/feedback/page-header"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"

const features = [
  { title: "多智能体分析", icon: TrendingUp, text: "基本面、技术面、新闻分析等智能体协作，提供多角度股票分析。" },
  { title: "智能股票筛选", icon: Search, text: "多维度筛选条件和结果表格，帮助发现符合策略的候选股票。" },
  { title: "专业分析报告", icon: FileText, text: "生成结构化分析报告，支持 Markdown 和图表内容展示。" },
  { title: "个性化配置", icon: Settings, text: "支持模型、数据源、缓存、同步、调度等系统配置。" }
]

const stacks = [
  { title: "前端技术", icon: Monitor, items: ["Next.js App Router", "React", "TypeScript", "Tailwind", "shadcn/ui + Radix"] },
  { title: "后端技术", icon: Cpu, items: ["FastAPI", "Python", "PostgreSQL", "Redis", "异步任务"] },
  { title: "AI 技术", icon: Star, items: ["多智能体系统", "大语言模型", "工具调用", "数据挖掘", "风险分析"] }
]

export function AboutPage() {
  return (
    <div>
      <PageHeader
        title="AGENTrader"
        description="现代化的多智能体股票分析学习平台。"
        actions={
          <div className="flex gap-2">
            <Button asChild><Link href="/analysis/single">开始分析</Link></Button>
            <Button variant="outline" asChild><Link href="/learning">查看文档</Link></Button>
          </div>
        }
      />
      <section className="rounded-md border bg-background p-6">
        <div className="flex flex-wrap items-center gap-3">
          <h2 className="text-xl font-semibold">AGENTrader</h2>
          <Badge>v1.0.1</Badge>
        </div>
        <p className="mt-4 max-w-4xl text-sm leading-7 text-muted-foreground">
          基于先进的 AI 技术，为投资者提供股票分析学习工具。系统采用多智能体协作模式，从基本面、技术面、新闻与风险等角度进行分析，帮助用户理解投资研究流程。分析结果仅供学习和参考，不构成投资建议。
        </p>
        <p className="mt-3 text-sm text-muted-foreground">
          AGENTrader 聚焦 AI 股票分析学习场景，强调数据复核、风险边界和多角色观点整合。
        </p>
      </section>
      <section className="mt-8">
        <h2 className="text-lg font-semibold">核心功能</h2>
        <div className="mt-4 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          {features.map((feature) => {
            const Icon = feature.icon
            return (
              <div key={feature.title} className="rounded-md border bg-background p-5">
                <Icon className="mb-4 size-5 text-primary" />
                <div className="font-medium">{feature.title}</div>
                <p className="mt-2 text-sm text-muted-foreground">{feature.text}</p>
              </div>
            )
          })}
        </div>
      </section>
      <section className="mt-8">
        <h2 className="text-lg font-semibold">技术架构</h2>
        <div className="mt-4 grid gap-4 md:grid-cols-3">
          {stacks.map((stack) => {
            const Icon = stack.icon
            return (
              <div key={stack.title} className="rounded-md border bg-background p-5">
                <Icon className="mb-4 size-5 text-primary" />
                <div className="font-medium">{stack.title}</div>
                <div className="mt-3 flex flex-wrap gap-2">
                  {stack.items.map((item) => <Badge key={item} variant="secondary">{item}</Badge>)}
                </div>
              </div>
            )
          })}
        </div>
      </section>
    </div>
  )
}
