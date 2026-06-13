"use client"

import { useEffect } from "react"
import type { Dispatch } from "react"
import { useSearchParams } from "next/navigation"

import { MARKETS, type Market } from "@/features/research/options"
import type { ResearchUiAction } from "@/features/research-agent/mode"

export function useAgentRouteMode({
  dispatchUi
}: {
  dispatchUi: Dispatch<ResearchUiAction>
}) {
  const searchParams = useSearchParams()
  const searchKey = searchParams?.toString() || ""
  const stockInitialSymbol = searchParams?.get("symbol") || searchParams?.get("stock") || ""
  const rawInitialMarket = searchParams?.get("market")
  const stockInitialMarket = MARKETS.includes(rawInitialMarket as Market) ? rawInitialMarket as Market : undefined
  const batchInitialSymbols = searchParams?.get("stocks") || ""

  useEffect(() => {
    const mode = searchParams?.get("mode")
    if (mode !== "stock" && mode !== "batch") return
    dispatchUi({ type: mode === "stock" ? "openStock" : "openBatch" })
  }, [dispatchUi, searchKey, searchParams])

  return {
    batchInitialSymbols,
    stockInitialMarket,
    stockInitialSymbol
  }
}
