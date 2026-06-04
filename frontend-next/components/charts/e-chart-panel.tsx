"use client"

import type { EChartsOption } from "echarts"
import ReactECharts from "echarts-for-react"
import { useTheme } from "next-themes"

import { EmptyState } from "@/components/feedback/empty-state"
import { cn } from "@/libs/utils"

interface EChartPanelProps {
  option?: EChartsOption
  loading?: boolean
  empty?: boolean
  emptyText?: string
  height?: number | string
  className?: string
}

export function EChartPanel({
  option,
  loading = false,
  empty = false,
  emptyText = "暂无图表数据",
  height = 360,
  className
}: EChartPanelProps) {
  const { resolvedTheme } = useTheme()
  const chartTheme = resolvedTheme === "dark" ? "dark" : undefined

  if (empty || !option) {
    return (
      <div className={cn("flex items-center justify-center rounded-md border bg-background", className)} style={{ height }}>
        <EmptyState title={emptyText} />
      </div>
    )
  }

  return (
    <div className={cn("rounded-md border bg-background p-3", className)}>
      <ReactECharts
        option={option}
        theme={chartTheme}
        showLoading={loading}
        loadingOption={{ text: "加载中..." }}
        notMerge
        lazyUpdate
        autoResize
        style={{ height, width: "100%" }}
      />
    </div>
  )
}
