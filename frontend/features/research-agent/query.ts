"use client"

import { useEffect } from "react"
import { useSearchParams } from "next/navigation"

import { MARKETS, type Market } from "@/features/research/options"

type ComposerMode = "chat" | "goal"

export function useAgentRouteMode({
  setBatchConfigSubmitted,
  setComposerMode,
  setShowBatchConfig,
  setShowStockConfig,
  setStockConfigSubmitted
}: {
  setBatchConfigSubmitted: (value: boolean) => void
  setComposerMode: (value: ComposerMode) => void
  setShowBatchConfig: (value: boolean) => void
  setShowStockConfig: (value: boolean) => void
  setStockConfigSubmitted: (value: boolean) => void
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
    setShowStockConfig(mode === "stock")
    setShowBatchConfig(mode === "batch")
    setStockConfigSubmitted(false)
    setBatchConfigSubmitted(false)
    setComposerMode("chat")
  }, [
    searchKey,
    searchParams,
    setBatchConfigSubmitted,
    setComposerMode,
    setShowBatchConfig,
    setShowStockConfig,
    setStockConfigSubmitted
  ])

  return {
    batchInitialSymbols,
    stockInitialMarket,
    stockInitialSymbol
  }
}
