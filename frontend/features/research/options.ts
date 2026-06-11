export const MARKETS = ["A股", "港股", "美股"] as const
export const DEPTHS = ["快速", "基础", "标准", "深度", "全面"] as const
export const ANALYSTS = [
  { id: "market", label: "市场" },
  { id: "fundamentals", label: "基本面" },
  { id: "news", label: "新闻" },
  { id: "social", label: "社媒" }
] as const

export type Market = typeof MARKETS[number]
export type Depth = typeof DEPTHS[number]
export type AnalystId = typeof ANALYSTS[number]["id"]
