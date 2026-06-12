export type StockAgentHrefParams = {
  symbol?: string
  stock?: string
  market?: string
}

export function stockAgentHref(params: StockAgentHrefParams = {}) {
  const search = new URLSearchParams()
  search.set("mode", "stock")

  const symbol = params.symbol || params.stock
  if (symbol) search.set("symbol", symbol)
  if (params.market) search.set("market", params.market)

  return `/agent?${search.toString()}`
}

export function batchAgentHref(params: { stocks?: string[] | string } = {}) {
  const search = new URLSearchParams()
  search.set("mode", "batch")

  const stocks = Array.isArray(params.stocks) ? params.stocks.join(",") : params.stocks
  if (stocks) search.set("stocks", stocks)

  return `/agent?${search.toString()}`
}
