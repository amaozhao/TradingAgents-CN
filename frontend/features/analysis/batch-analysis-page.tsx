"use client"

import { useEffect, useMemo, useState } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import { AlertTriangle, Play, RefreshCw, Trash2, X } from "lucide-react"
import { toast } from "sonner"

import { AsyncButton } from "@/components/feedback/async-button"
import { PageHeader } from "@/components/feedback/page-header"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { analysisApi } from "@/libs/api/analysis"
import { configApi } from "@/libs/api/config"
import { cn } from "@/libs/utils"

const analysts = [
  { id: "market", name: "市场分析师", description: "分析市场趋势、行业动态和宏观经济环境" },
  { id: "fundamentals", name: "基本面分析师", description: "分析公司财务状况、业务模式和竞争优势" },
  { id: "news", name: "新闻分析师", description: "分析相关新闻、公告和市场事件的影响" },
  { id: "social", name: "社媒分析师", description: "分析社交媒体情绪、投资者心理和舆论导向" }
]

const depthOptions = [
  { value: "1", label: "1级 - 快速分析", hint: "2-4分钟/只" },
  { value: "2", label: "2级 - 基础分析", hint: "4-6分钟/只" },
  { value: "3", label: "3级 - 标准分析", hint: "6-10分钟/只，推荐" },
  { value: "4", label: "4级 - 深度分析", hint: "10-15分钟/只" },
  { value: "5", label: "5级 - 全面分析", hint: "15-25分钟/只" }
]

type Market = "A股" | "港股" | "美股"

interface ParsedSymbol {
  symbol: string
  market: Market
}

function normalizeStockCode(raw: string): ParsedSymbol | null {
  const value = raw.trim().toUpperCase()
  if (!value) return null

  const aShare = value.match(/^(\d{6})(?:\.(SH|SZ|BJ|SSE|SZSE|BSE))?$/)
  if (aShare && ["60", "68", "00", "30", "43", "83", "87"].includes(aShare[1].slice(0, 2))) {
    return { symbol: aShare[1], market: "A股" }
  }

  const hkShare = value.match(/^(\d{1,5})(?:\.HK)?$/)
  if (hkShare) {
    return { symbol: hkShare[1].padStart(5, "0"), market: "港股" }
  }

  if (/^[A-Z]{1,5}(?:\.[A-Z])?$/.test(value)) {
    return { symbol: value, market: "美股" }
  }

  return null
}

function parseStockInput(input: string) {
  const parsed: ParsedSymbol[] = []
  const invalid: string[] = []
  const seen = new Set<string>()

  input
    .split(/[\n,，\s]+/)
    .map((item) => item.trim())
    .filter(Boolean)
    .forEach((item) => {
      const normalized = normalizeStockCode(item)
      if (!normalized) {
        invalid.push(item)
        return
      }
      if (seen.has(normalized.symbol)) return
      seen.add(normalized.symbol)
      parsed.push(normalized)
    })

  return { parsed, invalid }
}

function getSharedMarket(symbols: ParsedSymbol[]) {
  const markets = new Set(symbols.map((item) => item.market))
  return markets.size === 1 ? Array.from(markets)[0] : undefined
}

export function BatchAnalysisPage() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const initialStocks = searchParams.get("stocks")?.split(",").map((item) => item.trim()).filter(Boolean).join("\n") || ""
  const [title, setTitle] = useState("")
  const [description, setDescription] = useState("")
  const [stockInput, setStockInput] = useState(initialStocks)
  const [depth, setDepth] = useState("3")
  const [selectedAnalysts, setSelectedAnalysts] = useState<string[]>(["market", "fundamentals"])
  const [includeSentiment, setIncludeSentiment] = useState(true)
  const [includeRisk, setIncludeRisk] = useState(true)
  const [language, setLanguage] = useState("zh-CN")
  const [quickAnalysisModel, setQuickAnalysisModel] = useState("qwen-turbo")
  const [deepAnalysisModel, setDeepAnalysisModel] = useState("qwen-max")
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    configApi.getDefaultModels()
      .then((models) => {
        setQuickAnalysisModel(models.quick_analysis_model)
        setDeepAnalysisModel(models.deep_analysis_model)
      })
      .catch(() => {
        setQuickAnalysisModel("qwen-plus")
        setDeepAnalysisModel("qwen-max")
      })
  }, [])

  const { parsed, invalid } = useMemo(() => parseStockInput(stockInput), [stockInput])
  const symbols = parsed.map((item) => item.symbol)

  const handleRemoveSymbol = (symbol: string) => {
    setStockInput((current) => {
      const nextSymbols = parseStockInput(current).parsed
        .filter((item) => item.symbol !== symbol)
        .map((item) => item.symbol)
      return nextSymbols.join("\n")
    })
  }

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()

    if (!title.trim()) {
      toast.warning("请输入批次标题")
      return
    }

    if (!symbols.length) {
      toast.warning("请输入股票代码")
      return
    }

    if (symbols.length > 10) {
      toast.warning("单次批量分析最多支持10只股票，请减少股票数量")
      return
    }

    if (!selectedAnalysts.length) {
      toast.warning("请选择至少一个分析师")
      return
    }

    setSubmitting(true)
    try {
      const response = await analysisApi.startBatchAnalysis({
        title: title.trim(),
        description: description.trim() || undefined,
        symbols,
        stock_codes: symbols,
        parameters: {
          market_type: getSharedMarket(parsed),
          research_depth: depth,
          selected_analysts: selectedAnalysts,
          include_sentiment: includeSentiment,
          include_risk: includeRisk,
          language,
          quick_analysis_model: quickAnalysisModel,
          deep_analysis_model: deepAnalysisModel
        }
      })

      if (!response?.success) {
        throw new Error(response?.message || "批量分析提交失败")
      }

      const batchId = response.data.batch_id
      toast.success(`批量分析任务已提交：${response.data.total_tasks}只股票`)
      router.push(batchId ? `/tasks?batch_id=${encodeURIComponent(batchId)}` : "/tasks")
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "批量分析提交失败")
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div>
      <PageHeader title="批量分析" description="AI驱动的批量股票分析，高效处理多只股票。" />

      <div className="mb-5 rounded-md border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
        <div className="flex gap-2">
          <AlertTriangle className="mt-0.5 size-4 shrink-0" />
          <span>本工具为股票分析辅助工具，所有分析结果仅供参考，不构成投资建议。投资有风险，决策需谨慎。</span>
        </div>
      </div>

      <form className="space-y-5" onSubmit={handleSubmit}>
        <Card>
          <CardHeader className="flex-row items-center justify-between space-y-0">
            <CardTitle>股票列表</CardTitle>
            <Badge variant={symbols.length ? "default" : "secondary"}>{symbols.length} 只股票</Badge>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-2">
              <Label htmlFor="batch-symbols">股票代码列表</Label>
              <textarea
                id="batch-symbols"
                aria-label="股票代码列表"
                className="min-h-44 w-full rounded-md border bg-background px-3 py-2 text-sm"
                placeholder={"请输入股票代码，每行一个\n支持格式：\n000001\n000002.SZ\n600036.SH\nAAPL\nTSLA"}
                value={stockInput}
                onChange={(event) => setStockInput(event.target.value)}
              />
            </div>
            <div className="flex flex-wrap gap-2">
              <Button type="button" size="sm" onClick={() => setStockInput((current) => parseStockInput(current).parsed.map((item) => item.symbol).join("\n"))}>
                <RefreshCw className="size-4" />
                解析股票代码
              </Button>
              <Button type="button" size="sm" variant="outline" onClick={() => setStockInput("")}>
                <Trash2 className="size-4" />
                清空
              </Button>
            </div>
            {symbols.length ? (
              <div className="space-y-2">
                <div className="text-sm font-medium">股票预览</div>
                <div className="flex flex-wrap gap-2">
                  {symbols.map((symbol) => (
                    <Badge key={symbol} className="gap-1" variant="secondary">
                      {symbol}
                      <button aria-label={`移除 ${symbol}`} className="rounded-sm hover:text-destructive" type="button" onClick={() => handleRemoveSymbol(symbol)}>
                        <X className="size-3" />
                      </button>
                    </Badge>
                  ))}
                </div>
              </div>
            ) : null}
            {invalid.length ? (
              <div className="rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
                <div className="mb-2 font-medium">以下股票代码格式可能有误，请检查：</div>
                <div className="flex flex-wrap gap-2">
                  {invalid.map((code) => <Badge key={code} variant="destructive">{code}</Badge>)}
                </div>
              </div>
            ) : null}
          </CardContent>
        </Card>

        <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_320px]">
          <Card>
            <CardHeader><CardTitle>分析配置</CardTitle></CardHeader>
            <CardContent className="space-y-5">
              <div className="grid gap-4 md:grid-cols-2">
                <div className="grid gap-2">
                  <Label htmlFor="batch-title">批次标题</Label>
                  <Input id="batch-title" value={title} onChange={(event) => setTitle(event.target.value)} placeholder="如：银行板块分析" />
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="batch-depth">分析深度</Label>
                  <Select value={depth} onValueChange={setDepth}>
                    <SelectTrigger id="batch-depth"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      {depthOptions.map((item) => (
                        <SelectItem key={item.value} value={item.value}>{item.label}（{item.hint}）</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>

              <div className="grid gap-2">
                <Label htmlFor="batch-description">批次描述</Label>
                <textarea
                  id="batch-description"
                  aria-label="批次描述"
                  className="min-h-20 w-full rounded-md border bg-background px-3 py-2 text-sm"
                  placeholder="描述本次批量分析的目的和背景（可选）"
                  value={description}
                  onChange={(event) => setDescription(event.target.value)}
                />
              </div>

              <div className="grid gap-3">
                <Label>分析师团队</Label>
                <div className="grid gap-2 sm:grid-cols-2">
                  {analysts.map((analyst) => (
                    <label
                      key={analyst.id}
                      className={cn(
                        "flex gap-3 rounded-md border p-3 text-sm transition-colors",
                        selectedAnalysts.includes(analyst.id) ? "border-primary bg-primary/5" : "bg-background"
                      )}
                    >
                      <input
                        className="mt-1"
                        type="checkbox"
                        checked={selectedAnalysts.includes(analyst.id)}
                        onChange={(event) => {
                          setSelectedAnalysts((current) =>
                            event.target.checked ? [...current, analyst.id] : current.filter((item) => item !== analyst.id)
                          )
                        }}
                      />
                      <span>
                        <span className="block font-medium">{analyst.name}</span>
                        <span className="text-muted-foreground">{analyst.description}</span>
                      </span>
                    </label>
                  ))}
                </div>
              </div>

              <div className="flex justify-center pt-2">
                <AsyncButton className="h-12 min-w-72 text-base font-semibold" type="submit" loading={submitting} loadingText="提交中...">
                  <Play className="size-4" />
                  开始批量分析 ({symbols.length}只)
                </AsyncButton>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader><CardTitle>高级配置</CardTitle></CardHeader>
            <CardContent className="space-y-5">
              <div className="grid gap-2">
                <Label htmlFor="quick-model">快速分析模型</Label>
                <Input id="quick-model" value={quickAnalysisModel} onChange={(event) => setQuickAnalysisModel(event.target.value)} />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="deep-model">深度分析模型</Label>
                <Input id="deep-model" value={deepAnalysisModel} onChange={(event) => setDeepAnalysisModel(event.target.value)} />
              </div>
              <div className="space-y-3">
                <label className="flex items-start gap-3 text-sm">
                  <input className="mt-1" type="checkbox" checked={includeSentiment} onChange={(event) => setIncludeSentiment(event.target.checked)} />
                  <span><span className="block font-medium">情绪分析</span><span className="text-muted-foreground">分析市场情绪和投资者心理</span></span>
                </label>
                <label className="flex items-start gap-3 text-sm">
                  <input className="mt-1" type="checkbox" checked={includeRisk} onChange={(event) => setIncludeRisk(event.target.checked)} />
                  <span><span className="block font-medium">风险评估</span><span className="text-muted-foreground">包含详细的风险因素分析</span></span>
                </label>
              </div>
              <div className="grid gap-2">
                <Label htmlFor="batch-language">语言偏好</Label>
                <Select value={language} onValueChange={setLanguage}>
                  <SelectTrigger id="batch-language"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="zh-CN">中文</SelectItem>
                    <SelectItem value="en-US">English</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </CardContent>
          </Card>
        </div>
      </form>
    </div>
  )
}
