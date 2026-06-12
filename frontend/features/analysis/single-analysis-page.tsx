"use client"

import { zodResolver } from "@hookform/resolvers/zod"
import { AlertCircle, BarChart3, Check, Cpu, ExternalLink, FileText, Info, MessageCircle, Search, Settings, Shield, TrendingUp } from "lucide-react"
import Link from "next/link"
import { useRouter, useSearchParams } from "next/navigation"
import { useEffect, useMemo } from "react"
import { useForm, useWatch } from "react-hook-form"
import { toast } from "sonner"
import { z } from "zod"

import { AsyncButton } from "@/components/feedback/async-button"
import { PageHeader } from "@/components/feedback/page-header"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { DatePicker } from "@/components/ui/date-picker"
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { analysisApi } from "@/libs/api/analysis"
import { configApi, type LLMConfig } from "@/libs/api/config"
import { cn } from "@/libs/utils"
import { useQuery } from "@tanstack/react-query"

type MarketType = "A股" | "港股" | "美股"

const schema = z.object({
  market_type: z.enum(["A股", "港股", "美股"]),
  stock_symbol: z.string().min(1, "请输入股票代码"),
  analysis_date: z.string().min(1, "请选择分析日期"),
  research_depth: z.number().min(1).max(5),
  analysts: z.array(z.string()).min(1, "请选择至少一个分析师"),
  include_sentiment: z.boolean(),
  include_risk: z.boolean(),
  language: z.enum(["zh-CN", "en-US"]),
  quick_analysis_model: z.string().min(1, "请选择快速分析模型"),
  deep_analysis_model: z.string().min(1, "请选择深度决策模型")
})

type Values = z.infer<typeof schema>

const analysts = [
  { id: "market", name: "市场分析师", description: "分析市场趋势、行业动态和宏观经济环境", icon: TrendingUp },
  { id: "fundamentals", name: "基本面分析师", description: "分析公司财务状况、业务模式和竞争优势", icon: BarChart3 },
  { id: "news", name: "新闻分析师", description: "分析相关新闻、公告和市场事件的影响", icon: FileText },
  { id: "social", name: "社媒分析师", description: "分析社交媒体情绪、投资者心理和舆论导向", icon: MessageCircle }
]

const analystNameToId = new Map(analysts.map((analyst) => [analyst.name, analyst.id]))

const depthOptions = [
  { value: 1, icon: "⚡", name: "1级 - 快速分析", description: "基础数据概览，快速决策", time: "2-5分钟", label: "快速" },
  { value: 2, icon: "📈", name: "2级 - 基础分析", description: "常规投资决策", time: "3-6分钟", label: "基础" },
  { value: 3, icon: "🎯", name: "3级 - 标准分析", description: "技术+基本面，推荐", time: "4-8分钟", label: "标准" },
  { value: 4, icon: "🔍", name: "4级 - 深度分析", description: "多轮辩论，深度研究", time: "6-11分钟", label: "深度" },
  { value: 5, icon: "🏆", name: "5级 - 全面分析", description: "最全面的分析报告", time: "8-16分钟", label: "全面" }
]

const fallbackModels = [
  { provider: "dashscope", model_name: "qwen-turbo", model_display_name: "通义千问 Turbo", enabled: true, max_tokens: 2000, temperature: 0.7, timeout: 60, retry_times: 2 },
  { provider: "dashscope", model_name: "qwen-plus", model_display_name: "通义千问 Plus", enabled: true, max_tokens: 4000, temperature: 0.7, timeout: 60, retry_times: 2 },
  { provider: "dashscope", model_name: "qwen-max", model_display_name: "通义千问 Max", enabled: true, max_tokens: 8000, temperature: 0.7, timeout: 60, retry_times: 2 }
] satisfies LLMConfig[]

export function SingleAnalysisPage() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const initialMarket = normalizeMarket(searchParams.get("market"))
  const initialSymbol = searchParams.get("symbol") || searchParams.get("stock") || ""
  const inferredMarket = initialSymbol && !searchParams.get("market") ? getMarketByStockCode(initialSymbol) : initialMarket
  const modelsQuery = useQuery({
    queryKey: ["analysis", "llm-configs"],
    queryFn: () => configApi.getLLMConfigs(),
    retry: false
  })
  const modelOptions = useMemo(() => {
    const enabled = (modelsQuery.data || []).filter((model) => model.enabled)
    return enabled.length ? enabled : fallbackModels
  }, [modelsQuery.data])
  const configuredModelCount = useMemo(() => (modelsQuery.data || []).filter((model) => model.enabled).length, [modelsQuery.data])
  const usingFallbackModels = !configuredModelCount

  const form = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: {
      market_type: inferredMarket,
      stock_symbol: initialSymbol,
      analysis_date: new Date().toISOString().slice(0, 10),
      research_depth: 3,
      analysts: ["市场分析师", "基本面分析师"],
      include_sentiment: true,
      include_risk: true,
      language: "zh-CN",
      quick_analysis_model: "qwen-turbo",
      deep_analysis_model: "qwen-max"
    }
  })

  const market = useWatch({ control: form.control, name: "market_type" })
  const stockSymbol = useWatch({ control: form.control, name: "stock_symbol" })
  const researchDepth = useWatch({ control: form.control, name: "research_depth" })
  const selectedAnalysts = useWatch({ control: form.control, name: "analysts" })
  const validation = stockSymbol.trim() ? validateStockCode(stockSymbol, market) : null
  const selectedDepth = depthOptions.find((depth) => depth.value === researchDepth) || depthOptions[2]

  useEffect(() => {
    if (market === "A股" && selectedAnalysts.includes("社媒分析师")) {
      form.setValue("analysts", selectedAnalysts.filter((name) => name !== "社媒分析师"), { shouldValidate: true })
    }
  }, [form, market, selectedAnalysts])

  function updateMarket(value: MarketType) {
    form.setValue("market_type", value, { shouldValidate: true })
    if (value === "A股" && form.getValues("analysts").includes("社媒分析师")) {
      form.setValue("analysts", form.getValues("analysts").filter((name) => name !== "社媒分析师"), { shouldValidate: true })
    }
  }

  async function onSubmit(values: Values) {
    const stockValidation = validateStockCode(values.stock_symbol, values.market_type)
    if (!stockValidation.valid) {
      toast.error(stockValidation.message || "股票代码格式不正确")
      return
    }

    const symbol = stockValidation.normalizedCode || values.stock_symbol.trim().toUpperCase()
    await analysisApi.startSingleAnalysis({
      symbol,
      stock_code: symbol,
      parameters: {
        market_type: values.market_type,
        analysis_date: values.analysis_date,
        research_depth: getDepthDescription(values.research_depth),
        selected_analysts: values.analysts.map((name) => analystNameToId.get(name) || name),
        include_sentiment: values.include_sentiment,
        include_risk: values.include_risk,
        language: values.language,
        quick_analysis_model: values.quick_analysis_model,
        deep_analysis_model: values.deep_analysis_model
      }
    })
    toast.success("分析任务已提交，正在处理中...")
    router.push("/tasks")
  }

  return (
    <div>
      <PageHeader title="个股分析" description="AI驱动的智能股票分析，多维度评估投资价值与风险" />
      <Form {...form}>
        <form className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_360px]" onSubmit={form.handleSubmit(onSubmit)}>
          <Card>
            <CardHeader className="flex-row items-center justify-between gap-3">
              <CardTitle>分析配置</CardTitle>
              <Badge variant="secondary">必填信息</Badge>
            </CardHeader>
            <CardContent className="space-y-8">
              <section className="space-y-4">
                <SectionTitle icon="📊" title="股票信息" />
                <div className="grid gap-4 md:grid-cols-2">
                  <FormField
                    control={form.control}
                    name="stock_symbol"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>股票代码</FormLabel>
                        <FormControl>
                          <Input
                            placeholder="如：000001、AAPL、700、1810"
                            {...field}
                            onBlur={(event) => {
                              field.onBlur()
                              const result = validateStockCode(event.target.value, form.getValues("market_type"))
                              if (result.valid && result.market && result.market !== form.getValues("market_type")) {
                                form.setValue("market_type", result.market, { shouldValidate: true })
                                toast.success(`已自动识别为${result.market}`)
                              }
                              if (result.valid && result.normalizedCode) {
                                form.setValue("stock_symbol", result.normalizedCode, { shouldValidate: true })
                              }
                            }}
                          />
                        </FormControl>
                        {validation ? (
                          <p className={cn("text-xs", validation.valid ? "text-emerald-600" : "text-destructive")}>
                            {validation.valid ? `✓ ${validation.market}代码格式正确` : validation.message}
                          </p>
                        ) : (
                          <p className="text-xs text-muted-foreground">{getStockCodeFormatHelp(market)}</p>
                        )}
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <FormField
                    control={form.control}
                    name="market_type"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>市场类型</FormLabel>
                        <Select value={field.value} onValueChange={(value) => updateMarket(value as MarketType)}>
                          <FormControl>
                            <SelectTrigger><SelectValue /></SelectTrigger>
                          </FormControl>
                          <SelectContent>
                            <SelectItem value="A股">🇨🇳 A股市场（6位数字）</SelectItem>
                            <SelectItem value="美股">🇺🇸 美股市场（1-5个字母）</SelectItem>
                            <SelectItem value="港股">🇭🇰 港股市场（1-5位数字）</SelectItem>
                          </SelectContent>
                        </Select>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </div>
                <FormField
                  control={form.control}
                  name="analysis_date"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>分析日期</FormLabel>
                      <FormControl>
                        <DatePicker value={field.value} onChange={field.onChange} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </section>

              <section className="space-y-4">
                <SectionTitle icon="🎯" title="分析深度" />
                <FormField
                  control={form.control}
                  name="research_depth"
                  render={({ field }) => (
                    <FormItem>
                      <div className="grid gap-3 md:grid-cols-2">
                        {depthOptions.map((depth) => (
                          <button
                            key={depth.value}
                            type="button"
                            onClick={() => field.onChange(depth.value)}
                            className={cn(
                              "flex min-h-24 items-start gap-3 rounded-md border p-4 text-left transition-colors hover:border-primary/60 hover:bg-primary/5",
                              field.value === depth.value && "border-primary bg-primary/10"
                            )}
                          >
                            <span className="text-2xl" aria-hidden>{depth.icon}</span>
                            <span>
                              <span className="block font-medium">{depth.name}</span>
                              <span className="mt-1 block text-sm text-muted-foreground">{depth.description}</span>
                              <span className="mt-2 block text-xs text-muted-foreground">{depth.time}</span>
                            </span>
                          </button>
                        ))}
                      </div>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </section>

              <section className="space-y-4">
                <SectionTitle icon="👥" title="分析师团队" />
                <FormField
                  control={form.control}
                  name="analysts"
                  render={({ field }) => (
                    <FormItem>
                      <div className="grid gap-3 md:grid-cols-2">
                        {analysts.map((analyst) => {
                          const disabled = analyst.name === "社媒分析师" && market === "A股"
                          const active = field.value.includes(analyst.name)
                          const Icon = analyst.icon
                          return (
                            <button
                              key={analyst.id}
                              type="button"
                              disabled={disabled}
                              onClick={() => {
                                field.onChange(
                                  active
                                    ? field.value.filter((item) => item !== analyst.name)
                                    : [...field.value, analyst.name]
                                )
                              }}
                              className={cn(
                                "flex min-h-24 items-center gap-3 rounded-md border p-4 text-left transition-colors hover:border-primary/60 hover:bg-primary/5 disabled:cursor-not-allowed disabled:opacity-50",
                                active && "border-primary bg-primary/10"
                              )}
                            >
                              <span className="flex size-10 shrink-0 items-center justify-center rounded-md bg-primary/10 text-primary">
                                <Icon className="size-5" />
                              </span>
                              <span className="min-w-0 flex-1">
                                <span className="block font-medium">{analyst.name}</span>
                                <span className="mt-1 block text-sm text-muted-foreground">{analyst.description}</span>
                              </span>
                              {active ? <Check className="size-5 shrink-0 text-primary" /> : null}
                            </button>
                          )
                        })}
                      </div>
                      {market === "A股" ? (
                        <div className="flex items-start gap-2 rounded-md border border-sky-200 bg-sky-50 p-3 text-sm text-sky-900">
                          <Info className="mt-0.5 size-4 shrink-0" />
                          A股市场暂不支持社媒分析（国内数据源限制）
                        </div>
                      ) : null}
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </section>

              <div className="flex justify-center">
                <AsyncButton
                  type="submit"
                  loading={form.formState.isSubmitting}
                  loadingText="分析进行中..."
                  disabled={!stockSymbol.trim()}
                  className="h-14 min-w-72 text-base font-semibold"
                >
                  <TrendingUp className="size-5" />
                  开始智能分析
                </AsyncButton>
              </div>
            </CardContent>
          </Card>

          <aside className="space-y-6">
            <Card>
              <CardHeader className="flex-row items-center justify-between gap-3">
                <CardTitle>高级配置</CardTitle>
                <Badge variant="outline">可选设置</Badge>
              </CardHeader>
              <CardContent className="space-y-6">
                <section className="space-y-4">
                  <div className="flex items-start justify-between gap-3">
                    <SectionTitle icon="🤖" title="AI模型配置" compact />
                    <Button asChild variant="outline" size="sm">
                      <Link href="/settings/config?tab=llm">
                        <Settings className="size-4" />
                        配置模型
                      </Link>
                    </Button>
                  </div>
                  <div className="rounded-md border bg-muted/30 p-3 text-sm">
                    <div className="flex items-start gap-2">
                      <Cpu className="mt-0.5 size-4 shrink-0 text-primary" />
                      <div className="space-y-1">
                        <p className="font-medium">这里选择本次分析实际调用的 AI 模型。</p>
                        <p className="text-muted-foreground">先到“配置管理”添加厂家 API Key，再在“大模型配置”里启用模型；启用后会出现在下面两个下拉框。</p>
                      </div>
                    </div>
                  </div>
                  {usingFallbackModels ? (
                    <div className="rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
                      <div className="flex items-start gap-2">
                        <AlertCircle className="mt-0.5 size-4 shrink-0" />
                        <div>
                          <p className="font-medium">当前没有读取到已启用模型配置。</p>
                          <p className="mt-1">下拉框展示的是内置示例模型。正式分析前请先配置厂家密钥并启用模型。</p>
                          <Button asChild variant="outline" size="sm" className="mt-3 bg-background">
                            <Link href="/settings/config?tab=providers">
                              去配置厂家 API Key
                              <ExternalLink className="size-4" />
                            </Link>
                          </Button>
                        </div>
                      </div>
                    </div>
                  ) : (
                    <div className="rounded-md border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-900">
                      已读取 {configuredModelCount} 个已启用模型配置，可直接选择。
                    </div>
                  )}
                  <ModelSelect
                    name="quick_analysis_model"
                    label="快速分析模型"
                    description="用于行情、新闻、基本面等初筛步骤。建议选择速度快、成本低的模型。"
                    models={modelOptions}
                  />
                  <ModelSelect
                    name="deep_analysis_model"
                    label="深度决策模型"
                    description="用于综合推理、风险判断和最终结论。建议选择推理能力更强的模型。"
                    models={modelOptions}
                  />
                  <div className="rounded-md border bg-muted/40 p-3 text-sm text-muted-foreground">
                    <div className="font-medium text-foreground">推荐选择</div>
                    <p className="mt-1">{selectedDepth.label}分析：快速模型用 Turbo/Flash/轻量模型，深度模型用 Plus/Max/推理能力更强的模型。</p>
                    <p className="mt-1">如果只有一个可用模型，两个下拉框可以选择同一个模型。</p>
                  </div>
                </section>

                <section className="space-y-4">
                  <SectionTitle icon="⚙️" title="分析选项" compact />
                  <ToggleField name="include_sentiment" title="情绪分析" description="分析市场情绪和投资者心理" />
                  <ToggleField name="include_risk" title="风险评估" description="包含详细的风险因素分析" icon={Shield} />
                </section>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>分析说明</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3 text-sm text-muted-foreground">
                <p>多智能体团队会按所选深度协作完成市场、基本面、新闻和风险分析。</p>
                <p>分析结果由 AI 模型基于历史数据和公开信息生成，不构成投资建议。</p>
                <p>深度越高，耗时和模型成本越高。</p>
              </CardContent>
            </Card>
          </aside>
        </form>
      </Form>
    </div>
  )

  function ModelSelect({
    name,
    label,
    description,
    models
  }: {
    name: "quick_analysis_model" | "deep_analysis_model"
    label: string
    description: string
    models: LLMConfig[]
  }) {
    return (
      <FormField
        control={form.control}
        name={name}
        render={({ field }) => (
          <FormItem>
            <FormLabel>{label}</FormLabel>
            <p className="text-xs leading-5 text-muted-foreground">{description}</p>
            <Select value={field.value} onValueChange={field.onChange}>
              <FormControl>
                <SelectTrigger><SelectValue /></SelectTrigger>
              </FormControl>
              <SelectContent>
                {models.map((model) => (
                  <SelectItem key={`${name}-${model.provider}-${model.model_name}`} value={model.model_name}>
                    {model.model_display_name || model.model_name} · {model.provider}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <FormMessage />
          </FormItem>
        )}
      />
    )
  }

  function ToggleField({
    name,
    title,
    description,
    icon: Icon = Search
  }: {
    name: "include_sentiment" | "include_risk"
    title: string
    description: string
    icon?: typeof Search
  }) {
    return (
      <FormField
        control={form.control}
        name={name}
        render={({ field }) => (
          <FormItem>
            <button
              type="button"
              onClick={() => field.onChange(!field.value)}
              className={cn("flex w-full items-center gap-3 rounded-md border p-3 text-left", field.value && "border-primary bg-primary/10")}
            >
              <span className="flex size-9 shrink-0 items-center justify-center rounded-md bg-primary/10 text-primary">
                <Icon className="size-4" />
              </span>
              <span className="flex-1">
                <span className="block text-sm font-medium">{title}</span>
                <span className="mt-1 block text-xs text-muted-foreground">{description}</span>
              </span>
              <span className={cn("h-6 w-11 rounded-full p-1 transition-colors", field.value ? "bg-primary" : "bg-muted")}>
                <span className={cn("block size-4 rounded-full bg-background transition-transform", field.value && "translate-x-5")} />
              </span>
            </button>
          </FormItem>
        )}
      />
    )
  }
}

function SectionTitle({ icon, title, compact }: { icon: string; title: string; compact?: boolean }) {
  return (
    <div className={cn("flex items-center gap-2 font-semibold", compact ? "text-sm" : "text-base")}>
      <span aria-hidden>{icon}</span>
      <span>{title}</span>
    </div>
  )
}

function normalizeMarket(value: string | null): MarketType {
  const normalized = String(value || "").trim().toUpperCase()
  if (value === "港股" || normalized === "HK" || normalized === "HKEX") return "港股"
  if (value === "美股" || normalized === "US" || normalized === "NASDAQ" || normalized === "NYSE") return "美股"
  return "A股"
}

function getMarketByStockCode(code: string): MarketType {
  const value = code.trim().toUpperCase()
  if (/^\d{6}$/.test(value)) return "A股"
  if (/^\d{1,5}$/.test(value) || value.endsWith(".HK")) return "港股"
  if (/^[A-Z]{1,5}$/.test(value)) return "美股"
  return "A股"
}

function validateStockCode(code: string, market: MarketType): { valid: boolean; message?: string; market?: MarketType; normalizedCode?: string } {
  const value = code.trim().toUpperCase()
  if (!value) return { valid: false, message: "请输入股票代码" }

  if (market === "A股") {
    return /^\d{6}$/.test(value)
      ? { valid: true, market: "A股", normalizedCode: value }
      : { valid: false, message: "A股代码应为6位数字，如 000001、600519" }
  }
  if (market === "美股") {
    return /^[A-Z]{1,5}$/.test(value)
      ? { valid: true, market: "美股", normalizedCode: value }
      : { valid: false, message: "美股代码应为1-5个字母，如 AAPL、TSLA" }
  }
  const clean = value.replace(".HK", "").padStart(Math.min(value.replace(".HK", "").length, 5), "0")
  return /^\d{1,5}$/.test(value.replace(".HK", ""))
    ? { valid: true, market: "港股", normalizedCode: clean }
    : { valid: false, message: "港股代码应为1-5位数字，如 700、9988" }
}

function getStockCodeFormatHelp(market: MarketType) {
  if (market === "美股") return "1-5个字母，如：AAPL（苹果）、TSLA（特斯拉）"
  if (market === "港股") return "1-5位数字，如：700（腾讯）、9988（阿里巴巴）"
  return "6位数字，如：000001（平安银行）、600519（贵州茅台）"
}

function getDepthDescription(depth: number) {
  return depthOptions.find((item) => item.value === depth)?.label || "标准"
}
