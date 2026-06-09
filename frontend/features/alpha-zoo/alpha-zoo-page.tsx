"use client"

import { useEffect, useMemo, useState } from "react"
import Link from "next/link"
import { AlertTriangle, ArrowLeftRight, Layers, Play, Search } from "lucide-react"

import { PageHeader } from "@/components/feedback/page-header"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { AlphaFactorTable } from "@/features/alpha-zoo/alpha-factor-table"
import { alphaZooApi, type AlphaFactor } from "@/libs/api/alpha-zoo"
import { useAppStore, type AppLanguage } from "@/stores/app-store"

const ZOOS = [
  { id: "all", label: { "zh-CN": "全部因子库", "en-US": "All zoos" } },
  { id: "qlib158", label: { "zh-CN": "Qlib 158", "en-US": "Qlib 158" } },
  { id: "alpha101", label: { "zh-CN": "Kakushadze 101", "en-US": "Kakushadze 101 Formulaic Alphas" } },
  { id: "gtja191", label: { "zh-CN": "GTJA 191", "en-US": "GTJA 191" } },
  { id: "academic", label: { "zh-CN": "学术异常因子", "en-US": "Academic Anomalies" } }
]

const ZOO_CARDS = [
  {
    id: "qlib158",
    fallbackCount: 154,
    title: { "zh-CN": "Qlib 158", "en-US": "Qlib 158" },
    description: {
      "zh-CN": "Microsoft Qlib 的完整 158 特征体系，覆盖动量、波动率、成交量和滚动统计信号。",
      "en-US": "Microsoft Qlib's full 158-feature library covering momentum, volatility, volume and rolling statistical signals."
    }
  },
  {
    id: "alpha101",
    fallbackCount: 101,
    title: { "zh-CN": "Kakushadze 101 公式因子", "en-US": "Kakushadze 101 Formulaic Alphas" },
    description: {
      "zh-CN": "Kakushadze 2015 年提出的 101 个公式化 Alpha，偏短周期横截面信号。",
      "en-US": "The 101 formulaic alphas from Kakushadze (2015); short-horizon cross-sectional signals."
    }
  },
  {
    id: "gtja191",
    fallbackCount: 191,
    title: { "zh-CN": "GTJA 191", "en-US": "GTJA 191" },
    description: {
      "zh-CN": "国泰君安 191 个 Alpha 因子，包含适配中国 A 股市场的技术面与微观结构信号。",
      "en-US": "Guotai Junan Securities' 191 alphas; technical and microstructure signals tuned to China A-share markets."
    }
  },
  {
    id: "academic",
    fallbackCount: 6,
    title: { "zh-CN": "学术异常因子", "en-US": "Academic Anomalies" },
    description: {
      "zh-CN": "从学术文献整理的长期异常因子，覆盖价值、动量、质量、低波动等方向。",
      "en-US": "Curated long-horizon anomalies from the academic literature (value, momentum, quality, low-vol, etc.)."
    }
  }
]

const UNIVERSES = [
  { id: "all", label: { "zh-CN": "全部市场", "en-US": "All universes" } },
  { id: "equity_cn", label: { "zh-CN": "A 股", "en-US": "China A-shares" } },
  { id: "equity_us", label: { "zh-CN": "美股", "en-US": "US equities" } },
  { id: "equity_hk", label: { "zh-CN": "港股", "en-US": "HK equities" } },
  { id: "crypto", label: { "zh-CN": "Crypto", "en-US": "Crypto" } },
  { id: "futures", label: { "zh-CN": "Futures", "en-US": "Futures" } }
]

const COPY = {
  "zh-CN": {
    eyebrow: "ALPHA ZOO",
    title: "452 个预置量化 Alpha，覆盖 4 个因子库",
    description: "浏览来自 Qlib、Kakushadze 101、GTJA 191 和学术异常文献的公式化横截面信号。点击任意因子可进入详情查看公式和源码，也可以运行基准测试评估整个因子库。",
    pageTitle: "Alpha 因子库",
    pageDescription: "真实 Alpha 因子目录、筛选和基准测试入口。",
    search: "搜索",
    zoo: "因子库",
    theme: "主题",
    allThemes: "全部主题",
    universe: "市场",
    compare: "比较",
    compareHint: "至少选择两个因子后比较",
    runBenchmark: "运行基准测试",
    searchPlaceholder: "因子 ID / 名称 / 公式",
    loadError: "Alpha 因子库加载失败"
  },
  "en-US": {
    eyebrow: "ALPHA ZOO",
    title: "452 pre-built quant alphas across 4 zoos",
    description: "Browse formula-driven cross-sectional signals from Qlib, the Kakushadze 101 set, GTJA 191, and the academic anomaly literature. Click any alpha to read its formula and source code, or run a bench to score the whole zoo on a universe and period.",
    pageTitle: "Alpha Zoo",
    pageDescription: "Real alpha catalogue, filters, and benchmark entry points.",
    search: "Search",
    zoo: "Zoo",
    theme: "Theme",
    allThemes: "All themes",
    universe: "Universe",
    compare: "Compare",
    compareHint: "Select at least two factors to compare",
    runBenchmark: "Run benchmark",
    searchPlaceholder: "Alpha ID / name / formula",
    loadError: "Failed to load Alpha Zoo"
  }
} satisfies Record<AppLanguage, Record<string, string>>

export function AlphaZooPage() {
  const language = useAppStore((state) => state.language)
  const copy = COPY[language]
  const [items, setItems] = useState<AlphaFactor[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [zoo, setZoo] = useState("all")
  const [theme, setTheme] = useState("all")
  const [universe, setUniverse] = useState("all")
  const [search, setSearch] = useState("")
  const [selectedIds, setSelectedIds] = useState<Set<string>>(() => new Set())

  useEffect(() => {
    let alive = true

    const loadFactors = async () => {
      setLoading(true)
      setError(null)
      try {
        const response = await alphaZooApi.list({
          zoo: zoo === "all" ? undefined : zoo,
          theme: theme === "all" ? undefined : theme,
          universe: universe === "all" ? undefined : universe,
          search: search.trim() || undefined,
          limit: 1000
        })
        if (!alive) return
        setItems(response.data.items || response.data.alphas || [])
      } catch (err) {
        if (!alive) return
        setItems([])
        setError(err instanceof Error ? err.message : copy.loadError)
      } finally {
        if (alive) setLoading(false)
      }
    }

    void loadFactors()

    return () => {
      alive = false
    }
  }, [copy.loadError, search, theme, universe, zoo])

  const themeOptions = useMemo(() => {
    const values = new Set<string>()
    for (const item of items) {
      for (const itemTheme of item.theme) values.add(itemTheme)
    }
    return Array.from(values).sort()
  }, [items])

  const countsByZoo = useMemo(() => {
    const counts = new Map<string, number>()
    for (const item of items) counts.set(item.zoo, (counts.get(item.zoo) || 0) + 1)
    return counts
  }, [items])

  const toggleSelected = (factorId: string) => {
    setSelectedIds((current) => {
      const next = new Set(current)
      if (next.has(factorId)) next.delete(factorId)
      else next.add(factorId)
      return next
    })
  }

  return (
    <div className="mx-auto max-w-6xl space-y-8">
      <PageHeader title={copy.pageTitle} description={copy.pageDescription} />

      <section className="space-y-3">
        <div className="flex items-center gap-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
          <Layers className="size-3.5" />
          {copy.eyebrow}
        </div>
        <div className="max-w-3xl space-y-2">
          <h1 className="text-2xl font-bold tracking-tight md:text-3xl">{copy.title}</h1>
          <p className="text-sm leading-relaxed text-muted-foreground">{copy.description}</p>
        </div>
      </section>

      <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {ZOO_CARDS.map((card) => {
          const active = zoo === card.id
          const count = countsByZoo.get(card.id) || card.fallbackCount
          return (
            <button
              key={card.id}
              type="button"
              onClick={() => setZoo(active ? "all" : card.id)}
              className={`rounded-xl border bg-gradient-to-br from-card to-muted/30 p-4 text-left transition hover:border-primary/50 ${active ? "border-primary ring-1 ring-primary/30" : ""}`}
            >
              <div className="mb-3 flex items-start justify-between gap-4">
                <span className="font-mono text-lg font-semibold tabular-nums">{count}</span>
                <Layers className="size-5 text-primary" />
              </div>
              <h3 className="text-sm font-semibold leading-tight">{card.title[language]}</h3>
              <p className="mt-2 line-clamp-3 text-xs leading-relaxed text-muted-foreground">{card.description[language]}</p>
            </button>
          )
        })}
      </section>

      <section className="rounded-xl border bg-card p-4">
        <div className="grid gap-3 md:grid-cols-[minmax(260px,1fr)_180px_180px_190px_auto_auto] md:items-end">
          <div className="grid gap-1.5">
            <Label>{copy.search}</Label>
            <div className="relative">
              <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
              <Input className="pl-9" value={search} onChange={(event) => setSearch(event.target.value)} placeholder={copy.searchPlaceholder} />
            </div>
          </div>

          <div className="grid gap-1.5">
            <Label>{copy.zoo}</Label>
            <Select value={zoo} onValueChange={setZoo}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>{ZOOS.map((option) => <SelectItem key={option.id} value={option.id}>{option.label[language]}</SelectItem>)}</SelectContent>
            </Select>
          </div>

          <div className="grid gap-1.5">
            <Label>{copy.theme}</Label>
            <Select value={theme} onValueChange={setTheme}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="all">{copy.allThemes}</SelectItem>
                {themeOptions.map((option) => <SelectItem key={option} value={option}>{option}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>

          <div className="grid gap-1.5">
            <Label>{copy.universe}</Label>
            <Select value={universe} onValueChange={setUniverse}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>{UNIVERSES.map((option) => <SelectItem key={option.id} value={option.id}>{option.label[language]}</SelectItem>)}</SelectContent>
            </Select>
          </div>

          <Button variant="outline" title={copy.compareHint} disabled={selectedIds.size < 2} asChild={selectedIds.size >= 2}>
            {selectedIds.size >= 2 ? (
              <Link href={`/alpha-zoo/compare?ids=${Array.from(selectedIds).map(encodeURIComponent).join(",")}`}>
                <ArrowLeftRight className="mr-2 size-4" />{copy.compare} ({selectedIds.size})
              </Link>
            ) : (
              <span><ArrowLeftRight className="mr-2 inline size-4" />{copy.compare}</span>
            )}
          </Button>

          <Button asChild>
            <Link href={`/alpha-zoo/bench?zoo=${encodeURIComponent(zoo === "all" ? "alpha101" : zoo)}`}>
              <Play className="mr-2 size-4" />{copy.runBenchmark}
            </Link>
          </Button>
        </div>

        {error ? (
          <div className="mt-3 rounded-md border border-destructive/40 bg-destructive/5 p-3 text-sm text-destructive">
            <AlertTriangle className="mr-2 inline size-4" />{error}
          </div>
        ) : null}
      </section>

      <AlphaFactorTable factors={items} loading={loading} selectedIds={selectedIds} onToggleSelected={toggleSelected} />
    </div>
  )
}
