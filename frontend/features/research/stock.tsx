"use client"

import { useEffect, useMemo, useState } from "react"
import { BarChart3, ExternalLink, Play, Save, X } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { defaultStockModels, enabledModels, modelLabel } from "@/features/research/models"
import { ANALYSTS, DEPTHS, MARKETS, type Depth, type Market } from "@/features/research/options"
import {
  buildStockPayload,
  createStockDraft,
  localDateKey,
  stockDraftSummary,
  stockPayloadSummary,
  type StockDraft,
  type StockPayload,
  type StockSubmit
} from "@/features/research/payload"
import { normalizeStockSymbol, stockSymbolError } from "@/features/research/symbol"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue
} from "@/components/ui/select"
import { configApi, type LLMConfig } from "@/libs/api/config"

export type { StockPayload, StockSubmit }

export type StockRunStatus = {
  status: "running" | "ok" | "warning" | "error" | "skipped"
  preview?: string
  taskId?: string
  reportUrl?: string
}

function runStatusText(runStatus?: StockRunStatus) {
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

export function StockReplayCard({
  content,
  payload,
  runStatus
}: {
  content: string
  payload: StockPayload
  runStatus?: StockRunStatus
}) {
  return (
    <section className="rounded-lg border bg-background p-4 text-sm shadow-sm" aria-label="单股分析历史配置">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <BarChart3 className="size-4 text-primary" />
            <h2 className="text-sm font-semibold">单股分析</h2>
          </div>
          <p className="mt-1 break-words text-xs text-muted-foreground">{stockPayloadSummary(payload)}</p>
        </div>
        <span className="rounded-md border bg-muted/30 px-2 py-1 text-xs">
          当前状态：{runStatusText(runStatus)}
        </span>
      </div>
      {content && <p className="mt-3 whitespace-pre-wrap text-xs text-muted-foreground">{content}</p>}
      <dl className="mt-3 grid gap-2 text-xs md:grid-cols-3">
        <div className="rounded-md border px-2 py-1">
          <dt className="text-muted-foreground">分析日期</dt>
          <dd className="font-medium">{payload.analysis_date}</dd>
        </div>
        <div className="rounded-md border px-2 py-1">
          <dt className="text-muted-foreground">等待策略</dt>
          <dd className="font-medium">
            {payload.wait_for_completion ? `${payload.wait_timeout_seconds}s` : "只提交任务"}
          </dd>
        </div>
        <div className="rounded-md border px-2 py-1">
          <dt className="text-muted-foreground">补充问题</dt>
          <dd className="truncate font-medium">{payload.custom_prompt || "无"}</dd>
        </div>
      </dl>
      {runStatus?.preview && (
        <p className="mt-3 break-words rounded-md border bg-muted/20 px-3 py-2 text-xs text-muted-foreground">
          {runStatus.preview}
        </p>
      )}
      <div className="mt-3 flex flex-wrap gap-2 text-xs">
        {runStatus?.taskId && (
          <span className="inline-flex items-center rounded-md border bg-muted/20 px-2 py-1 text-muted-foreground">
            任务：{runStatus.taskId}
          </span>
        )}
        {runStatus?.taskId && (
          <a
            className="inline-flex items-center gap-1 rounded-md border bg-background px-2 py-1 hover:bg-muted"
            href={`/tasks?task_id=${encodeURIComponent(runStatus.taskId)}`}
          >
            查看任务<ExternalLink className="size-3" />
          </a>
        )}
        {runStatus?.reportUrl && (
          <a
            className="inline-flex items-center gap-1 rounded-md border bg-background px-2 py-1 hover:bg-muted"
            href={runStatus.reportUrl}
          >
            查看报告<ExternalLink className="size-3" />
          </a>
        )}
      </div>
    </section>
  )
}

export function StockConfigCard({
  running,
  locked = false,
  runStatus,
  onCancel,
  onSave,
  onSubmit
}: {
  running: boolean
  locked?: boolean
  runStatus?: StockRunStatus
  onCancel: () => void
  onSave: (summary: string) => void
  onSubmit: (value: StockSubmit) => void
}) {
  const [draft, setDraft] = useState<StockDraft>(() => createStockDraft())
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

  const normalized = useMemo(
    () => normalizeStockSymbol(draft.symbol, draft.market),
    [draft.symbol, draft.market]
  )
  const effectiveAnalysts = normalized.market === "A股"
    ? draft.analysts.filter((id) => id !== "social")
    : draft.analysts
  const effectiveDraft = { ...draft, analysts: effectiveAnalysts }
  const summary = stockDraftSummary(effectiveDraft, normalized)
  const error = stockSymbolError(normalized.symbol, normalized.market)
  const dateError = draft.date > localDateKey() ? "分析日期不能晚于今天。" : ""
  const analystError = effectiveAnalysts.length === 0 ? "至少选择一个分析师。" : ""
  const modelError = modelsError
    || (!modelsLoaded ? "正在加载模型配置。" : "")
    || (models.length === 0 ? "没有启用模型，请先在设置中配置模型。" : "")
    || (!draft.quick || !draft.deep ? "请选择快速分析模型和深度决策模型。" : "")
  const blockingError = error || dateError || analystError || modelError
  const disabled = running || locked

  function update<K extends keyof StockDraft>(key: K, value: StockDraft[K]) {
    setDraft((current) => ({ ...current, [key]: value }))
  }

  function toggleAnalyst(id: string) {
    if (id === "social" && normalized.market === "A股") return
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
    onSubmit({ summary, payload: buildStockPayload(effectiveDraft, normalized) })
  }

  return (
    <section className="rounded-lg border bg-background p-4 shadow-sm" aria-label="单股分析配置">
      <div className="grid gap-3">
        <div className="min-w-0 pr-2">
          <div className="flex items-center gap-2">
            <BarChart3 className="size-4 text-primary" />
            <h2 className="text-sm font-semibold">单股分析</h2>
          </div>
          <p className="mt-1 break-words text-xs text-muted-foreground">{summary}</p>
        </div>
        {blockingError && (
          <p className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-xs text-destructive">
            {blockingError}
          </p>
        )}
        {locked && !blockingError && (
          <p className="rounded-md border border-primary/30 bg-primary/10 px-3 py-2 text-xs text-primary">
            已提交，执行步骤和报告链接会在右侧更新。
          </p>
        )}
      </div>

      {locked && (
        <div className="mt-3 rounded-md border bg-muted/30 px-3 py-2 text-xs">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-medium">当前状态：{runStatusText(runStatus)}</span>
            {runStatus?.taskId && <span className="text-muted-foreground">任务：{runStatus.taskId}</span>}
          </div>
          {runStatus?.preview && (
            <p className="mt-1 break-words text-muted-foreground">{runStatus.preview}</p>
          )}
          <div className="mt-2 flex flex-wrap gap-2">
            {runStatus?.taskId && (
              <a
                className="inline-flex items-center gap-1 rounded-md border bg-background px-2 py-1 text-xs hover:bg-muted"
                href={`/tasks?task_id=${encodeURIComponent(runStatus.taskId)}`}
              >
                查看任务<ExternalLink className="size-3" />
              </a>
            )}
            {runStatus?.reportUrl && (
              <a
                className="inline-flex items-center gap-1 rounded-md border bg-background px-2 py-1 text-xs hover:bg-muted"
                href={runStatus.reportUrl}
              >
                查看报告<ExternalLink className="size-3" />
              </a>
            )}
          </div>
        </div>
      )}

      <div className="mt-4 grid gap-3 lg:grid-cols-3">
        <label className="grid content-start gap-1 text-xs font-medium">
          <span>股票代码</span>
          <Input
            value={draft.symbol}
            onChange={(event) => update("symbol", event.target.value)}
            onBlur={() => {
              update("symbol", normalized.symbol)
              update("market", normalized.market)
            }}
            placeholder="600519 / 0700.HK / AAPL"
            disabled={disabled}
          />
          <FieldNote error={Boolean(error)}>{error || (draft.symbol ? `规范化：${normalized.symbol} / ${normalized.market}` : "")}</FieldNote>
        </label>
        <label className="grid content-start gap-1 text-xs font-medium">
          <span>市场类型</span>
          <Select
            value={draft.market}
            onValueChange={(value) => update("market", value as Market)}
            disabled={disabled}
          >
            <SelectTrigger><SelectValue /></SelectTrigger>
            <SelectContent>
              {MARKETS.map((market) => <SelectItem key={market} value={market}>{market}</SelectItem>)}
            </SelectContent>
          </Select>
          <FieldNote>自动识别后可手动调整</FieldNote>
        </label>
        <label className="grid content-start gap-1 text-xs font-medium">
          <span>分析日期</span>
          <Input
            type="date"
            value={draft.date}
            max={localDateKey()}
            onChange={(event) => update("date", event.target.value)}
            disabled={disabled}
          />
          <FieldNote error={Boolean(dateError)}>{dateError}</FieldNote>
        </label>
      </div>

      <div className="mt-3 grid gap-3 lg:grid-cols-[12rem_minmax(0,1fr)]">
        <label className="grid content-start gap-1 text-xs font-medium">
          <span>分析深度</span>
          <Select
            value={draft.depth}
            onValueChange={(value) => update("depth", value as Depth)}
            disabled={disabled}
          >
            <SelectTrigger><SelectValue /></SelectTrigger>
            <SelectContent>
              {DEPTHS.map((depth) => <SelectItem key={depth} value={depth}>{depth}</SelectItem>)}
            </SelectContent>
          </Select>
          <FieldNote />
        </label>
        <fieldset className="grid gap-2 text-xs font-medium">
          <legend>分析师团队</legend>
          <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
            {ANALYSTS.map((analyst) => {
              const optionDisabled = disabled || (analyst.id === "social" && normalized.market === "A股")
              const checked = effectiveAnalysts.includes(analyst.id)
              return (
                <label
                  key={analyst.id}
                  className="inline-flex h-9 min-w-0 items-center gap-2 rounded-md border px-3 text-sm"
                >
                  <input
                    type="checkbox"
                    checked={checked}
                    disabled={optionDisabled}
                    onChange={() => toggleAnalyst(analyst.id)}
                  />
                  {analyst.label}
                </label>
              )
            })}
          </div>
          <FieldNote>{normalized.market === "A股" ? "A 股默认禁用社媒分析。" : ""}</FieldNote>
        </fieldset>
      </div>

      <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <label className="flex h-10 items-center justify-between rounded-md border px-3 text-sm">
          情绪分析
          <input
            type="checkbox"
            checked={draft.sentiment}
            disabled={disabled}
            onChange={(event) => update("sentiment", event.target.checked)}
          />
        </label>
        <label className="flex h-10 items-center justify-between rounded-md border px-3 text-sm">
          风险评估
          <input
            type="checkbox"
            checked={draft.risk}
            disabled={disabled}
            onChange={(event) => update("risk", event.target.checked)}
          />
        </label>
        <label className="flex h-10 items-center justify-between rounded-md border px-3 text-sm">
          等待完成
          <input
            type="checkbox"
            checked={draft.wait}
            disabled={disabled}
            onChange={(event) => update("wait", event.target.checked)}
          />
        </label>
        <label className="grid content-start gap-1 text-xs font-medium">
          <span>等待秒数</span>
          <Input
            type="number"
            min={30}
            max={1800}
            value={draft.timeout}
            disabled={disabled || !draft.wait}
            onChange={(event) => update("timeout", Number(event.target.value) || 900)}
          />
          <FieldNote>{draft.wait ? "30-1800 秒" : "未启用等待完成"}</FieldNote>
        </label>
      </div>

      <div className="mt-3 grid gap-3 md:grid-cols-2">
        <label className="grid content-start gap-1 text-xs font-medium">
          <span>快速分析模型</span>
          <Select
            value={draft.quick}
            onValueChange={(value) => update("quick", value)}
            disabled={disabled || models.length === 0}
          >
            <SelectTrigger><SelectValue /></SelectTrigger>
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
        <label className="grid content-start gap-1 text-xs font-medium">
          <span>深度决策模型</span>
          <Select
            value={draft.deep}
            onValueChange={(value) => update("deep", value)}
            disabled={disabled || models.length === 0}
          >
            <SelectTrigger><SelectValue /></SelectTrigger>
            <SelectContent>
              {models.map((model) => (
                <SelectItem key={`${model.provider}-${model.model_name}`} value={model.model_name}>
                  {modelLabel(model)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <FieldNote>{modelsError}</FieldNote>
        </label>
      </div>

      <label className="mt-3 grid gap-1 text-xs font-medium">
        补充问题
        <textarea
          value={draft.prompt}
          maxLength={1000}
          onChange={(event) => update("prompt", event.target.value)}
          disabled={disabled}
          className="min-h-20 rounded-md border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary/30"
          placeholder="例如：重点解释估值和风险"
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
          <Play className="size-4" />{running ? "运行中" : locked ? "已提交" : "开始分析"}
        </Button>
      </div>
    </section>
  )
}
