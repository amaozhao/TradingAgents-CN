"use client"

import { useEffect, useMemo, useState } from "react"
import { BarChart3, Play, Save, X } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { defaultStockModels, enabledModels, modelLabel } from "@/features/research/models"
import { ANALYSTS, DEPTHS, type Depth } from "@/features/research/options"
import {
  batchDraftSummary,
  batchPayloadSummary,
  buildBatchPayload,
  createBatchDraft,
  type BatchDraft,
  type BatchPayload,
  type BatchSubmit,
  type BatchSymbol
} from "@/features/research/payload"
import { configApi, type LLMConfig } from "@/libs/api/config"
import { cn } from "@/libs/utils/cn"

export type { BatchPayload, BatchSubmit }

export type BatchRunStatus = {
  status: "running" | "ok" | "warning" | "error" | "skipped"
  preview?: string
  taskId?: string
  reportUrl?: string
}

function normalizeBatchSymbol(raw: string): BatchSymbol | null {
  const value = raw.trim().toUpperCase()
  if (!value) return null

  const aShare = value.match(/^(?:SH|SZ|BJ|SSE|SZSE|BSE)?(\d{6})(?:\.(SH|SZ|BJ|SSE|SZSE|BSE))?$/)
  if (aShare && ["60", "68", "00", "30", "43", "83", "87"].includes(aShare[1].slice(0, 2))) {
    return { symbol: aShare[1], market: "A股" }
  }

  const hkShare = value.match(/^(?:HK)?(\d{1,5})(?:\.HK)?$/)
  if (hkShare) return { symbol: hkShare[1], market: "港股" }

  const usShare = value.match(/^([A-Z]{1,5})(?:\.(US|NASDAQ|NYSE|AMEX))?$/)
  if (usShare) return { symbol: usShare[1], market: "美股" }

  return null
}

function parseBatchSymbols(input: string) {
  const symbols: BatchSymbol[] = []
  const invalid: string[] = []
  const seen = new Set<string>()
  for (const item of input.split(/[\n,，\s]+/).map((value) => value.trim()).filter(Boolean)) {
    const normalized = normalizeBatchSymbol(item)
    if (!normalized) {
      invalid.push(item)
      continue
    }
    if (seen.has(normalized.symbol)) continue
    seen.add(normalized.symbol)
    symbols.push(normalized)
  }
  return { symbols, invalid }
}

function runStatusText(runStatus?: BatchRunStatus) {
  if (runStatus?.status === "ok") return "已完成"
  if (runStatus?.status === "error") return "失败"
  if (runStatus?.status === "skipped") return "已跳过"
  if (runStatus?.status === "warning") return "需要关注"
  return "运行中"
}

function FieldNote({
  children,
  error = false
}: {
  children?: string
  error?: boolean
}) {
  return (
    <span className={`min-h-4 text-[11px] leading-4 ${error ? "text-destructive" : "text-muted-foreground"}`}>
      {children || ""}
    </span>
  )
}

export function BatchReplayCard({
  content,
  payload,
  runStatus
}: {
  content: string
  payload: BatchPayload
  runStatus?: BatchRunStatus
}) {
  return (
    <section className="rounded-lg border bg-background p-4 text-sm shadow-sm" aria-label="批量分析历史配置">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <BarChart3 className="size-4 text-primary" />
            <h2 className="text-sm font-semibold">批量分析</h2>
          </div>
          <p className="mt-1 break-words text-xs text-muted-foreground">{batchPayloadSummary(payload)}</p>
        </div>
        <span className="rounded-md border bg-muted/30 px-2 py-1 text-xs">
          当前状态：{runStatusText(runStatus)}
        </span>
      </div>
      {content && <p className="mt-3 whitespace-pre-wrap text-xs text-muted-foreground">{content}</p>}
      <dl className="mt-3 grid gap-2 text-xs md:grid-cols-3">
        <div className="rounded-md border px-2 py-1">
          <dt className="text-muted-foreground">股票数量</dt>
          <dd className="font-medium">{payload.symbols.length}</dd>
        </div>
        <div className="rounded-md border px-2 py-1">
          <dt className="text-muted-foreground">分析日期</dt>
          <dd className="font-medium">{payload.analysis_date}</dd>
        </div>
        <div className="rounded-md border px-2 py-1">
          <dt className="text-muted-foreground">等待策略</dt>
          <dd className="font-medium">{payload.wait_for_completion ? "等待完成" : "只提交批次"}</dd>
        </div>
      </dl>
      {runStatus?.preview && (
        <p className="mt-3 break-words rounded-md border bg-muted/20 px-3 py-2 text-xs text-muted-foreground">
          {runStatus.preview}
        </p>
      )}
    </section>
  )
}

export function BatchConfigCard({
  running,
  locked = false,
  runStatus,
  onCancel,
  onSave,
  onSubmit
}: {
  running: boolean
  locked?: boolean
  runStatus?: BatchRunStatus
  onCancel: () => void
  onSave: (summary: string) => void
  onSubmit: (value: BatchSubmit) => void
}) {
  const [draft, setDraft] = useState<BatchDraft>(() => createBatchDraft())
  const [models, setModels] = useState<LLMConfig[]>([])
  const [modelsLoaded, setModelsLoaded] = useState(false)
  const [modelsError, setModelsError] = useState("")

  useEffect(() => {
    let active = true
    configApi.getLLMConfigs()
      .then((items) => {
        if (!active) return
        const enabled = enabledModels(items)
        const defaults = defaultStockModels(enabled)
        setModels(enabled)
        setModelsLoaded(true)
        setModelsError("")
        if (enabled.length) {
          setDraft((current) => ({
            ...current,
            quick: current.quick || defaults.quick,
            deep: current.deep || defaults.deep
          }))
        }
      })
      .catch(() => {
        if (!active) return
        setModelsLoaded(true)
        setModelsError("模型配置加载失败，请检查设置。")
      })
    return () => {
      active = false
    }
  }, [])

  const parsed = useMemo(() => parseBatchSymbols(draft.symbols), [draft.symbols])
  const summary = batchDraftSummary(draft, parsed.symbols)
  const titleError = draft.title.trim() ? "" : "请输入批次标题。"
  const symbolError = parsed.symbols.length === 0
    ? "请输入 1-10 个有效股票代码。"
    : parsed.symbols.length > 10
      ? "单次批量分析最多支持 10 只股票。"
      : ""
  const invalidError = draft.strict && parsed.invalid.length > 0
    ? `存在无效股票代码：${parsed.invalid.join("、")}`
    : ""
  const analystError = draft.analysts.length === 0 ? "至少选择一个分析师。" : ""
  const modelConfigError = modelsError
    || (!modelsLoaded ? "正在加载模型配置。" : "")
    || (models.length === 0 ? "没有启用模型，请先在设置中配置模型。" : "")
  const modelSelectionError = !modelConfigError && (!draft.quick || !draft.deep)
    ? "请选择快速分析模型和深度决策模型。"
    : ""
  const modelError = modelConfigError || modelSelectionError
  const blockingError = titleError || symbolError || invalidError || analystError || modelError
  const disabled = running || locked

  function update<K extends keyof BatchDraft>(key: K, value: BatchDraft[K]) {
    setDraft((current) => ({ ...current, [key]: value }))
  }

  function toggleAnalyst(id: string) {
    setDraft((current) => {
      const exists = current.analysts.includes(id)
      const analysts = exists
        ? current.analysts.filter((item) => item !== id)
        : [...current.analysts, id]
      return { ...current, analysts }
    })
  }

  function submit() {
    if (blockingError) return
    onSubmit({ summary, payload: buildBatchPayload(draft, parsed.symbols) })
  }

  return (
    <section className="rounded-lg border bg-background p-4 shadow-sm" aria-label="批量分析配置">
      <div className="grid gap-3">
        <div className="min-w-0 pr-2">
          <div className="flex items-center gap-2">
            <BarChart3 className="size-4 text-primary" />
            <h2 className="text-sm font-semibold">批量分析</h2>
          </div>
          <p className="mt-1 break-words text-xs text-muted-foreground">{summary}</p>
        </div>
        {modelConfigError && (
          <p className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-xs text-destructive">
            {modelConfigError}
          </p>
        )}
        {locked && !blockingError && (
          <p className="rounded-md border border-primary/30 bg-primary/10 px-3 py-2 text-xs text-primary">
            已提交，批量任务进度会在右侧执行步骤中更新。
          </p>
        )}
      </div>

      {locked && (
        <div className="mt-3 rounded-md border bg-muted/30 px-3 py-2 text-xs">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-medium">当前状态：{runStatusText(runStatus)}</span>
          </div>
          {runStatus?.preview && <p className="mt-1 break-words text-muted-foreground">{runStatus.preview}</p>}
        </div>
      )}

      <div className="mt-4 grid gap-3 [grid-template-columns:repeat(auto-fit,minmax(min(100%,18rem),1fr))]">
        <label className="grid min-w-0 content-start gap-1 text-xs font-medium">
          <span>批次标题</span>
          <Input
            className="min-w-0 max-w-full"
            aria-label="批次标题"
            value={draft.title}
            onChange={(event) => update("title", event.target.value)}
            placeholder="如：银行板块批量分析"
            disabled={disabled}
          />
          <FieldNote error={Boolean(titleError)}>{titleError}</FieldNote>
        </label>
        <label className="grid min-w-0 content-start gap-1 text-xs font-medium">
          <span>股票代码列表</span>
          <textarea
            aria-label="股票代码列表"
            value={draft.symbols}
            onChange={(event) => update("symbols", event.target.value)}
            disabled={disabled}
            className="min-h-24 min-w-0 max-w-full rounded-md border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary/30"
            placeholder={"每行一个，最多 10 个\n000001\n600519\nAAPL"}
          />
          <FieldNote error={Boolean(symbolError || invalidError)}>
            {symbolError || invalidError || `已识别 ${parsed.symbols.length} 只股票`}
          </FieldNote>
        </label>
      </div>

      <div className="mt-4 grid gap-3 [grid-template-columns:repeat(auto-fit,minmax(min(100%,18rem),1fr))]">
        <div className="grid min-w-0 content-start gap-2 rounded-md border bg-muted/10 p-3">
          <label className="grid min-w-0 content-start gap-1 text-xs font-medium">
            <span>分析深度</span>
            <Select
              value={draft.depth}
              onValueChange={(value) => update("depth", value as Depth)}
              disabled={disabled}
            >
              <SelectTrigger className="min-w-0 [&>span]:truncate"><SelectValue /></SelectTrigger>
              <SelectContent>
                {DEPTHS.map((depth) => <SelectItem key={depth} value={depth}>{depth}</SelectItem>)}
              </SelectContent>
            </Select>
          </label>
          <FieldNote>每个子任务沿用 Agent 个股 workflow。</FieldNote>
        </div>
        <fieldset className="grid min-w-0 gap-2 rounded-md border bg-muted/10 p-3 text-xs font-medium">
          <legend className="px-1">分析师团队</legend>
          <div className="grid gap-2 [grid-template-columns:repeat(auto-fit,minmax(min(100%,8rem),1fr))]">
            {ANALYSTS.map((analyst) => {
              const checked = draft.analysts.includes(analyst.id)
              return (
                <label
                  key={analyst.id}
                  className={cn(
                    "grid min-h-11 min-w-0 grid-cols-[minmax(0,1fr)_auto] items-center gap-3 rounded-md border bg-background px-3 py-2 text-sm",
                    checked && "border-primary bg-primary/10",
                    disabled && "cursor-not-allowed opacity-55"
                  )}
                >
                  <span className="min-w-0 break-words leading-5">{analyst.label}</span>
                  <input
                    className="size-4 shrink-0 accent-primary"
                    type="checkbox"
                    checked={checked}
                    disabled={disabled}
                    onChange={() => toggleAnalyst(analyst.id)}
                  />
                </label>
              )
            })}
          </div>
          <FieldNote error={Boolean(analystError)}>{analystError}</FieldNote>
        </fieldset>
      </div>

      <fieldset className="mt-4 grid gap-3 rounded-md border bg-muted/10 p-3">
        <legend className="px-1 text-xs font-medium">执行选项</legend>
        <div className="grid items-stretch gap-3 [grid-template-columns:repeat(auto-fit,minmax(min(100%,11rem),1fr))]">
          <label className="grid min-h-16 min-w-0 grid-cols-[minmax(0,1fr)_auto] items-center gap-3 rounded-md border bg-background px-3 py-3 text-sm">
            <span className="min-w-0 break-words leading-5">情绪分析</span>
            <input
              className="size-4 shrink-0 accent-primary"
              type="checkbox"
              checked={draft.sentiment}
              disabled={disabled}
              onChange={(event) => update("sentiment", event.target.checked)}
            />
          </label>
          <label className="grid min-h-16 min-w-0 grid-cols-[minmax(0,1fr)_auto] items-center gap-3 rounded-md border bg-background px-3 py-3 text-sm">
            <span className="min-w-0 break-words leading-5">风险评估</span>
            <input
              className="size-4 shrink-0 accent-primary"
              type="checkbox"
              checked={draft.risk}
              disabled={disabled}
              onChange={(event) => update("risk", event.target.checked)}
            />
          </label>
          <label className="grid min-h-16 min-w-0 grid-cols-[minmax(0,1fr)_auto] items-center gap-3 rounded-md border bg-background px-3 py-3 text-sm">
            <span className="min-w-0 break-words leading-5">严格校验股票代码</span>
            <input
              className="size-4 shrink-0 accent-primary"
              type="checkbox"
              checked={draft.strict}
              disabled={disabled}
              onChange={(event) => update("strict", event.target.checked)}
            />
          </label>
          <label className="grid min-h-16 min-w-0 grid-cols-[minmax(0,1fr)_auto] items-center gap-3 rounded-md border bg-background px-3 py-3 text-sm">
            <span className="min-w-0 break-words leading-5">等待批次完成</span>
            <input
              className="size-4 shrink-0 accent-primary"
              type="checkbox"
              checked={draft.wait}
              disabled={disabled}
              onChange={(event) => update("wait", event.target.checked)}
            />
          </label>
        </div>
      </fieldset>

      <div className="mt-3 grid gap-3 [grid-template-columns:repeat(auto-fit,minmax(min(100%,16rem),1fr))]">
        <label className="grid min-w-0 content-start gap-1 text-xs font-medium">
          <span>最大并发</span>
          <Input
            type="number"
            min={1}
            max={3}
            value={draft.concurrency}
            disabled={disabled}
            onChange={(event) => update("concurrency", Math.min(3, Math.max(1, Number(event.target.value) || 1)))}
          />
          <FieldNote>后端会按系统上限再次约束。</FieldNote>
        </label>
        <label className="grid min-w-0 content-start gap-1 text-xs font-medium">
          <span>快速分析模型</span>
          <Select
            value={draft.quick}
            onValueChange={(value) => update("quick", value)}
            disabled={disabled || models.length === 0}
          >
            <SelectTrigger className="min-w-0 [&>span]:truncate"><SelectValue /></SelectTrigger>
            <SelectContent>
              {models.map((model) => (
                <SelectItem key={`${model.provider}-${model.model_name}`} value={model.model_name}>
                  {modelLabel(model)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <FieldNote />
        </label>
        <label className="grid min-w-0 content-start gap-1 text-xs font-medium">
          <span>深度决策模型</span>
          <Select
            value={draft.deep}
            onValueChange={(value) => update("deep", value)}
            disabled={disabled || models.length === 0}
          >
            <SelectTrigger className="min-w-0 [&>span]:truncate"><SelectValue /></SelectTrigger>
            <SelectContent>
              {models.map((model) => (
                <SelectItem key={`${model.provider}-${model.model_name}`} value={model.model_name}>
                  {modelLabel(model)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <FieldNote error={Boolean(modelSelectionError)}>{modelSelectionError}</FieldNote>
        </label>
      </div>

      <label className="mt-3 grid gap-1 text-xs font-medium">
        批次描述
        <textarea
          aria-label="批次描述"
          value={draft.description}
          maxLength={1000}
          onChange={(event) => update("description", event.target.value)}
          disabled={disabled}
          className="min-h-20 rounded-md border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary/30"
          placeholder="例如：重点比较银行股基本面和风险"
        />
      </label>

      <div className="mt-4 flex flex-wrap justify-end gap-2">
        <Button type="button" variant="outline" onClick={onCancel} disabled={running}>
          <X className="size-4" />取消
        </Button>
        <Button type="button" variant="secondary" onClick={() => onSave(summary)} disabled={disabled}>
          <Save className="size-4" />保存到输入框
        </Button>
        <Button type="button" onClick={submit} disabled={disabled || Boolean(blockingError)}>
          <Play className="size-4" />{running ? "运行中" : locked ? "已提交" : "开始批量分析"}
        </Button>
      </div>
    </section>
  )
}
