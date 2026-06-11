import { ANALYSTS, type Depth, type Market } from "@/features/research/options"
import type { NormalizedStockSymbol } from "@/features/research/symbol"

export type StockPayload = {
  mode: "single"
  symbol: string
  market_type: Market
  analysis_date: string
  research_depth: Depth
  selected_analysts: string[]
  include_sentiment: boolean
  include_risk: boolean
  language: "zh-CN"
  quick_analysis_model: string
  deep_analysis_model: string
  custom_prompt: string
  wait_for_completion: boolean
  wait_timeout_seconds: number
}

export type StockDraft = {
  symbol: string
  market: Market
  date: string
  depth: Depth
  analysts: string[]
  sentiment: boolean
  risk: boolean
  quick: string
  deep: string
  prompt: string
  wait: boolean
  timeout: number
}

export type StockSubmit = {
  summary: string
  payload: StockPayload
}

export function localDateKey(date = new Date()) {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, "0")
  const day = String(date.getDate()).padStart(2, "0")
  return `${year}-${month}-${day}`
}

export function createStockDraft(date = localDateKey()): StockDraft {
  return {
    symbol: "",
    market: "A股",
    date,
    depth: "标准",
    analysts: ["market", "fundamentals"],
    sentiment: true,
    risk: true,
    quick: "",
    deep: "",
    prompt: "",
    wait: true,
    timeout: 900
  }
}

export function stockDraftSummary(draft: StockDraft, normalized: NormalizedStockSymbol) {
  const analysts = draft.analysts
    .map((id) => ANALYSTS.find((item) => item.id === id)?.label || id)
    .join("+")
  const sentiment = draft.sentiment ? "情绪" : "无情绪"
  const risk = draft.risk ? "风险" : "无风险"
  return [
    normalized.symbol || "未填写代码",
    normalized.market,
    draft.depth,
    analysts || "未选分析师",
    `${sentiment}+${risk}`,
    `${draft.quick} -> ${draft.deep}`
  ].join(" / ")
}

export function buildStockPayload(
  draft: StockDraft,
  normalized: NormalizedStockSymbol
): StockPayload {
  return {
    mode: "single",
    symbol: normalized.symbol,
    market_type: normalized.market,
    analysis_date: draft.date,
    research_depth: draft.depth,
    selected_analysts: draft.analysts,
    include_sentiment: draft.sentiment,
    include_risk: draft.risk,
    language: "zh-CN",
    quick_analysis_model: draft.quick,
    deep_analysis_model: draft.deep,
    custom_prompt: draft.prompt.trim(),
    wait_for_completion: draft.wait,
    wait_timeout_seconds: draft.timeout
  }
}

export function stockPayloadSummary(payload: StockPayload) {
  const analysts = payload.selected_analysts.join("+") || "未选分析师"
  const sentiment = payload.include_sentiment ? "情绪" : "无情绪"
  const risk = payload.include_risk ? "风险" : "无风险"
  return [
    payload.symbol,
    payload.market_type,
    payload.research_depth,
    analysts,
    `${sentiment}+${risk}`,
    `${payload.quick_analysis_model} -> ${payload.deep_analysis_model}`
  ].join(" / ")
}
