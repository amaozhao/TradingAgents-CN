import type { Market } from "@/features/research/options"

export type NormalizedStockSymbol = {
  symbol: string
  market: Market
}

export function normalizeStockSymbol(raw: string, market: Market): NormalizedStockSymbol {
  const symbol = raw.trim().toUpperCase()
  const aPrefix = symbol.match(/^(SH|SZ|BJ|SSE|SZSE|BSE)(\d{6})$/)
  if (aPrefix) return { symbol: aPrefix[2], market: "A股" }
  const aSuffix = symbol.match(/^(\d{6})\.(SH|SZ|BJ|SSE|SZSE|BSE)$/)
  if (aSuffix) return { symbol: aSuffix[1], market: "A股" }
  if (/^\d{6}$/.test(symbol)) return { symbol, market }
  const hkPrefix = symbol.match(/^HK(\d{1,5})$/)
  if (hkPrefix) return { symbol: hkPrefix[1], market: "港股" }
  const hkSuffix = symbol.match(/^(\d{1,5})\.HK$/)
  if (hkSuffix) return { symbol: hkSuffix[1], market: "港股" }
  if (/^\d{1,5}$/.test(symbol)) return { symbol, market: market === "A股" ? "港股" : market }
  const usSuffix = symbol.match(/^([A-Z]{1,5})\.(US|NASDAQ|NYSE|AMEX)$/)
  if (usSuffix) return { symbol: usSuffix[1], market: "美股" }
  if (/^[A-Z]{1,5}$/.test(symbol)) return { symbol, market: "美股" }
  return { symbol, market }
}

export function stockSymbolError(symbol: string, market: Market) {
  if (!symbol) return "请输入股票代码。"
  if (market === "A股" && !/^\d{6}$/.test(symbol)) return "A股代码需要是 6 位数字。"
  if (market === "港股" && !/^\d{1,5}$/.test(symbol)) return "港股代码需要是 1-5 位数字。"
  if (market === "美股" && !/^[A-Z]{1,5}$/.test(symbol)) return "美股代码需要是 1-5 位字母。"
  return ""
}
