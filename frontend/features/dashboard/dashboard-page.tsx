"use client"

import Link from "next/link"
import { useMemo } from "react"
import { useQuery } from "@tanstack/react-query"
import type { ColumnDef } from "@tanstack/react-table"
import { ArrowRight, BarChart3, BookOpen, FileText, ListChecks, Search, Star, TrendingUp } from "lucide-react"

import { DataTable } from "@/components/data-table/data-table"
import { PageHeader } from "@/components/feedback/page-header"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { analysisApi } from "@/libs/api/analysis"
import type { FavoriteItem } from "@/libs/api/favorites"
import { favoritesApi } from "@/libs/api/favorites"
import type { NewsItem } from "@/libs/api/news"
import { newsApi } from "@/libs/api/news"
import { paperApi, type PaperAccountSummary } from "@/libs/api/paper"
import { formatDateTime } from "@/libs/utils/datetime"
import { useAuthStore } from "@/stores/auth-store"

type MaybeApiResponse<T> = T | { data: T }

function unwrap<T>(value: MaybeApiResponse<T>): T {
  return value && typeof value === "object" && "data" in value ? value.data : value
}

interface AnalysisRow {
  id?: string
  analysis_id?: string
  stock_code?: string
  stock_symbol?: string
  stock_name?: string
  status?: string
  start_time?: string
  created_at?: string
}

const recentColumns: ColumnDef<AnalysisRow>[] = [
  {
    accessorKey: "stock_code",
    header: "股票代码",
    cell: ({ row }) => row.original.stock_code || row.original.stock_symbol || "-"
  },
  {
    accessorKey: "stock_name",
    header: "股票名称",
    cell: ({ row }) => row.original.stock_name || "-"
  },
  {
    accessorKey: "status",
    header: "状态",
    cell: ({ row }) => <Badge variant={row.original.status === "completed" ? "default" : "secondary"}>{formatStatus(row.original.status)}</Badge>
  },
  {
    accessorKey: "created_at",
    header: "创建时间",
    cell: ({ row }) => formatDateTime(row.original.start_time || row.original.created_at || "")
  }
]

export function DashboardPage() {
  const user = useAuthStore((state) => state.user)
  const stats = useMemo(
    () => ({
      totalAnalyses: Number(user?.total_analyses || 0),
      successfulAnalyses: Number(user?.successful_analyses || 0),
      dailyQuota: Number(user?.daily_quota || 1000),
      concurrentLimit: Number(user?.concurrent_limit || 3)
    }),
    [user]
  )

  const recentQuery = useQuery({
    queryKey: ["dashboard", "recent-analysis"],
    queryFn: async () =>
      unwrap<{ items?: AnalysisRow[]; records?: AnalysisRow[] } | AnalysisRow[]>(
        (await analysisApi.getHistory({ page: 1, page_size: 5 })) as MaybeApiResponse<
          { items?: AnalysisRow[]; records?: AnalysisRow[] } | AnalysisRow[]
        >
      ),
    retry: false
  })

  const favoritesQuery = useQuery({
    queryKey: ["dashboard", "favorites"],
    queryFn: async () => unwrap<FavoriteItem[]>(await favoritesApi.list()),
    retry: false
  })

  const newsQuery = useQuery({
    queryKey: ["dashboard", "news"],
    queryFn: async () => unwrap(await newsApi.getLatestNews(undefined, 5, 24)),
    retry: false
  })

  const paperQuery = useQuery({
    queryKey: ["dashboard", "paper-account"],
    queryFn: async () => unwrap(await paperApi.getAccount()),
    retry: false
  })

  const recentRows = Array.isArray(recentQuery.data)
    ? recentQuery.data
    : recentQuery.data?.items || recentQuery.data?.records || []
  const favorites = favoritesQuery.data || []
  const news = newsQuery.data?.news || []
  const account = paperQuery.data?.account

  return (
    <div>
      <PageHeader
        title="欢迎使用 AGENTrader"
        description="现代化的多智能体股票分析学习平台，辅助你掌握更全面的市场视角。"
        actions={
          <>
            <Button asChild>
              <Link href="/analysis/single">
                <TrendingUp className="size-4" />
                快速分析
              </Link>
            </Button>
            <Button asChild variant="outline">
              <Link href="/screening">
                <Search className="size-4" />
                股票筛选
              </Link>
            </Button>
          </>
        }
      />

      <section className="mb-6 grid gap-4 md:grid-cols-4">
        <MetricCard title="总分析数" value={stats.totalAnalyses} />
        <MetricCard title="成功分析" value={stats.successfulAnalyses} />
        <MetricCard title="每日额度" value={stats.dailyQuota} />
        <MetricCard title="并发限制" value={stats.concurrentLimit} />
      </section>

      <Card className="mb-6">
        <CardContent className="flex flex-col gap-4 p-6 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <div className="mb-2 flex items-center gap-2 text-lg font-semibold">
              <BookOpen className="size-5" />
              AI股票分析学习中心
            </div>
            <p className="max-w-3xl text-sm text-muted-foreground">
              从零开始学习 AI、大语言模型和智能股票分析，理解多智能体系统如何协作分析股票。
            </p>
          </div>
          <Button asChild>
            <Link href="/learning">开始学习</Link>
          </Button>
        </CardContent>
      </Card>

      <div className="grid gap-6 lg:grid-cols-[2fr_1fr]">
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>快速操作</CardTitle>
            </CardHeader>
            <CardContent className="grid gap-3 sm:grid-cols-2">
              <ActionLink href="/analysis/single" icon={FileText} title="单股分析" description="深度分析单只股票" />
              <ActionLink href="/analysis/batch" icon={BarChart3} title="批量分析" description="同时分析多只股票" />
              <ActionLink href="/screening" icon={Search} title="股票筛选" description="多维条件筛选股票" />
              <ActionLink href="/tasks" icon={ListChecks} title="任务中心" description="查看和管理分析任务" />
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>最近分析</CardTitle>
            </CardHeader>
            <CardContent>
              <DataTable
                columns={recentColumns}
                data={recentRows}
                loading={recentQuery.isLoading}
                emptyText="暂无最近分析"
                enableToolbar={false}
                enablePagination={false}
              />
              <div className="mt-3 text-right">
                <Button asChild variant="ghost" size="sm">
                  <Link href="/tasks?tab=completed">查看全部历史</Link>
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>

        <div className="space-y-6">
          <SideList title="我的自选股" href="/favorites" emptyText="暂无自选股">
            {favorites.slice(0, 5).map((stock) => (
              <Link key={stock.stock_code} href={`/stocks/${stock.stock_code}`} className="flex items-center justify-between rounded-md border p-3">
                <span>
                  <span className="block text-sm font-medium">{stock.stock_code}</span>
                  <span className="text-xs text-muted-foreground">{stock.stock_name}</span>
                </span>
                <Star className="size-4 text-primary" />
              </Link>
            ))}
          </SideList>

          <SideList title="市场快讯" href="/learning" emptyText="暂无市场快讯">
            {news.map((item: NewsItem) => (
              <a key={item.id || item.title} href={item.url || "#"} target="_blank" rel="noreferrer" className="block rounded-md border p-3">
                <span className="line-clamp-2 text-sm font-medium">{item.title}</span>
                <span className="text-xs text-muted-foreground">{item.source || "新闻"}</span>
              </a>
            ))}
          </SideList>

          <PaperAccountCard account={account} />
        </div>
      </div>
    </div>
  )
}

function MetricCard({ title, value }: { title: string; value: number }) {
  return (
    <Card>
      <CardContent className="p-4">
        <div className="text-sm text-muted-foreground">{title}</div>
        <div className="mt-2 text-2xl font-semibold">{value}</div>
      </CardContent>
    </Card>
  )
}

function ActionLink({ href, icon: Icon, title, description }: { href: string; icon: typeof FileText; title: string; description: string }) {
  return (
    <Link href={href} className="flex items-center gap-3 rounded-md border p-4 transition-colors hover:bg-muted">
      <Icon className="size-5 text-primary" />
      <span className="min-w-0 flex-1">
        <span className="block font-medium">{title}</span>
        <span className="text-sm text-muted-foreground">{description}</span>
      </span>
      <ArrowRight className="size-4 text-muted-foreground" />
    </Link>
  )
}

function SideList({ title, href, emptyText, children }: { title: string; href: string; emptyText: string; children: React.ReactNode }) {
  const hasChildren = Array.isArray(children) ? children.length > 0 : Boolean(children)

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle>{title}</CardTitle>
        <Button asChild variant="ghost" size="sm">
          <Link href={href}>查看全部</Link>
        </Button>
      </CardHeader>
      <CardContent className="space-y-2">
        {hasChildren ? children : <div className="rounded-md border p-6 text-center text-sm text-muted-foreground">{emptyText}</div>}
      </CardContent>
    </Card>
  )
}

function PaperAccountCard({ account }: { account?: PaperAccountSummary }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>模拟交易账户</CardTitle>
      </CardHeader>
      <CardContent>
        {account ? (
          <div className="space-y-2 text-sm">
            <div className="flex justify-between"><span>现金</span><span>{formatMoney(account.cash)}</span></div>
            <div className="flex justify-between"><span>持仓市值</span><span>{formatMoney(account.positions_value)}</span></div>
            <div className="flex justify-between font-semibold"><span>总资产</span><span>{formatMoney(account.equity)}</span></div>
          </div>
        ) : (
          <div className="rounded-md border p-6 text-center text-sm text-muted-foreground">暂无账户信息</div>
        )}
      </CardContent>
    </Card>
  )
}

function formatStatus(status?: string) {
  const map: Record<string, string> = {
    completed: "已完成",
    running: "运行中",
    pending: "等待中",
    failed: "失败"
  }
  return status ? map[status] ?? status : "-"
}

function formatMoney(value: PaperAccountSummary["cash"]) {
  if (typeof value === "number") return `¥${value.toFixed(2)}`
  const cny = value?.CNY ?? 0
  return `¥${Number(cny).toFixed(2)}`
}
