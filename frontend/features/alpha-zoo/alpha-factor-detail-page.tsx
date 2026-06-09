"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { ArrowLeft, Play } from "lucide-react"
import katex from "katex"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { alphaZooApi, type AlphaFactorDetail } from "@/libs/api/alpha-zoo"
import { useAppStore, type AppLanguage } from "@/stores/app-store"

const COPY = {
  "zh-CN": {
    back: "返回 Alpha 因子库",
    runBenchmark: "运行该因子测试",
    formula: "公式",
    metadata: "元数据",
    sourceCode: "源码",
    viewSource: "查看源码",
    lineUnit: "行",
    loading: "正在加载因子详情...",
    error: "因子详情加载失败",
    theme: "主题",
    universe: "市场",
    frequency: "频率",
    decay: "衰减天数",
    warmup: "最小预热K线",
    requiresSector: "需要行业数据",
    modulePath: "模块路径",
    notes: "备注",
    columns: "依赖字段",
    extras: "额外依赖"
  },
  "en-US": {
    back: "Back to Alpha Zoo",
    runBenchmark: "Run this factor",
    formula: "Formula",
    metadata: "Metadata",
    sourceCode: "Source code",
    viewSource: "View source",
    lineUnit: "lines",
    loading: "Loading alpha details...",
    error: "Failed to load alpha detail",
    theme: "Theme",
    universe: "Universe",
    frequency: "Frequency",
    decay: "Decay (days)",
    warmup: "Min warm-up bars",
    requiresSector: "Requires sector",
    modulePath: "Module path",
    notes: "Notes",
    columns: "Required columns",
    extras: "Extra inputs"
  }
} satisfies Record<AppLanguage, Record<string, string>>

function listValue(values?: unknown[]) {
  return values?.length ? values.join(", ") : "-"
}

function boolValue(value: boolean) {
  return value ? "true" : "false"
}

function readableSummary(factor: AlphaFactorDetail) {
  if (factor.nickname) return factor.nickname
  if (factor.name && factor.name !== factor.id) return factor.name
  if (factor.description && factor.description !== factor.formula_latex) return factor.description
  return "-"
}

function sourceLineCount(source?: string) {
  const trimmed = source?.trim()
  return trimmed ? trimmed.split(/\r?\n/).length : 0
}

function renderFormula(formula?: string | null) {
  if (!formula) return ""

  return katex.renderToString(formula, {
    displayMode: true,
    throwOnError: false,
    strict: false,
    trust: false
  })
}

function MetadataRow({ label, value }: { label: string; value: string | number | null | undefined }) {
  return (
    <div className="grid gap-1 border-b py-3 last:border-b-0 sm:grid-cols-[180px_1fr] sm:gap-4">
      <dt className="text-sm font-medium text-muted-foreground">{label}</dt>
      <dd className="break-words text-sm">{value ?? "-"}</dd>
    </div>
  )
}

export function AlphaFactorDetailPage({ alphaId }: { alphaId: string }) {
  const language = useAppStore((state) => state.language)
  const copy = COPY[language]
  const [factor, setFactor] = useState<AlphaFactorDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let alive = true

    const loadFactor = async () => {
      setLoading(true)
      setError(null)
      try {
        const response = await alphaZooApi.detail(alphaId)
        if (alive) setFactor(response.data)
      } catch (err) {
        if (alive) setError(err instanceof Error ? err.message : copy.error)
      } finally {
        if (alive) setLoading(false)
      }
    }

    void loadFactor()

    return () => {
      alive = false
    }
  }, [alphaId, copy.error])

  if (loading) {
    return <div className="mx-auto max-w-5xl py-10 text-sm text-muted-foreground">{copy.loading}</div>
  }

  if (error || !factor) {
    return (
      <div className="mx-auto max-w-5xl space-y-4 py-10">
        <Button variant="outline" asChild>
          <Link href="/alpha-zoo"><ArrowLeft className="mr-2 size-4" />{copy.back}</Link>
        </Button>
        <Card>
          <CardContent className="pt-6 text-sm text-destructive">{error || copy.error}</CardContent>
        </Card>
      </div>
    )
  }

  const formula = factor.formula_latex || ""
  const sourceLines = sourceLineCount(factor.source_code)

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Button variant="outline" asChild>
          <Link href="/alpha-zoo"><ArrowLeft className="mr-2 size-4" />{copy.back}</Link>
        </Button>
        <Button asChild>
          <Link href={`/alpha-zoo/bench?alpha_id=${encodeURIComponent(factor.id)}&zoo=${encodeURIComponent(factor.zoo)}`}>
            <Play className="mr-2 size-4" />{copy.runBenchmark}
          </Link>
        </Button>
      </div>

      <section className="space-y-3">
        <div className="flex flex-wrap items-center gap-2">
          <h1 className="font-mono text-2xl font-bold tracking-tight md:text-3xl">{factor.id}</h1>
          <Badge variant="secondary">{factor.zoo}</Badge>
        </div>
        <p className="max-w-3xl text-sm leading-relaxed text-muted-foreground" data-testid="alpha-detail-summary">
          {readableSummary(factor)}
        </p>
      </section>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">{copy.formula}</CardTitle>
        </CardHeader>
        <CardContent>
          {formula ? (
            <div
              aria-label={formula}
              className="overflow-x-auto rounded-md border bg-muted/40 px-4 py-5 text-sm [&_.katex-display]:my-0 [&_.katex]:text-base"
              data-testid="alpha-detail-formula"
              dangerouslySetInnerHTML={{ __html: renderFormula(formula) }}
            />
          ) : (
            <div className="rounded-md border bg-muted/40 p-4 text-sm text-muted-foreground">-</div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">{copy.metadata}</CardTitle>
        </CardHeader>
        <CardContent>
          <dl>
            <MetadataRow label={copy.theme} value={listValue(factor.theme)} />
            <MetadataRow label={copy.universe} value={listValue(factor.universe)} />
            <MetadataRow label={copy.frequency} value={listValue(factor.frequency)} />
            <MetadataRow label={copy.decay} value={factor.decay_horizon} />
            <MetadataRow label={copy.warmup} value={factor.min_warmup_bars} />
            <MetadataRow label={copy.requiresSector} value={boolValue(factor.requires_sector)} />
            <MetadataRow label={copy.modulePath} value={factor.module_path || factor.alpha?.module_path} />
            <MetadataRow label={copy.columns} value={listValue(factor.columns_required || factor.required_columns)} />
            <MetadataRow label={copy.extras} value={listValue(factor.extras_required)} />
            <MetadataRow label={copy.notes} value={factor.notes || "-"} />
          </dl>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">{copy.sourceCode}</CardTitle>
        </CardHeader>
        <CardContent>
          <details className="rounded-md border bg-muted/40">
            <summary className="cursor-pointer px-4 py-3 text-sm font-medium text-foreground">
              {copy.viewSource} ({sourceLines} {copy.lineUnit})
            </summary>
            <pre className="max-h-[520px] overflow-auto border-t p-4 text-xs leading-relaxed">
              <code>{factor.source_code || "-"}</code>
            </pre>
          </details>
        </CardContent>
      </Card>
    </div>
  )
}
