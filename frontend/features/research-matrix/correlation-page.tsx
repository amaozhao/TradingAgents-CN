"use client"

import { useMemo, useState } from "react"
import type { EChartsOption } from "echarts"
import { BarChart3 } from "lucide-react"

import { EChartPanel } from "@/components/charts/e-chart-panel"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { researchMatrixApi } from "@/libs/api/research-matrix"
import { useAppStore, type AppLanguage } from "@/stores/app-store"

const WINDOWS = [30, 60, 90, 180, 365] as const
const METHODS = ["pearson", "spearman"] as const

const COPY = {
  "zh-CN": {
    title: "相关性矩阵",
    assetCodes: "资产代码",
    assetHint: "用英文逗号分隔 ticker，例如 BTC-USDT,ETH-USDT,AAPL,SPY 或 600519,000001,300750。",
    window: "窗口（天）",
    method: "方法",
    compute: "计算",
    loading: "加载中...",
    error: "相关性计算失败",
    noData: "暂无相关性数据",
    tooltipName: "相关性"
  },
  "en-US": {
    title: "Correlation Matrix",
    assetCodes: "Asset codes",
    assetHint: "Comma-separated ticker symbols, e.g. BTC-USDT,ETH-USDT,AAPL,SPY or 600519,000001,300750.",
    window: "Window (days)",
    method: "Method",
    compute: "Compute",
    loading: "Loading...",
    error: "Failed to compute correlation",
    noData: "No correlation data",
    tooltipName: "Correlation"
  }
} satisfies Record<AppLanguage, Record<string, string>>

type Method = (typeof METHODS)[number]

export function CorrelationPage() {
  const language = useAppStore((state) => state.language)
  const copy = COPY[language]
  const [codes, setCodes] = useState("BTC-USDT,ETH-USDT,SPY,AAPL")
  const [days, setDays] = useState<number>(90)
  const [method, setMethod] = useState<Method>("pearson")
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [labels, setLabels] = useState<string[]>([])
  const [matrix, setMatrix] = useState<number[][]>([])

  const compute = async () => {
    const symbols = codes.split(",").map((item) => item.trim()).filter(Boolean)
    setError(null)
    setLoading(true)
    try {
      const response = await researchMatrixApi.correlation({ symbols, method, window: days })
      const resultMatrix = response.data.result?.matrix || {}
      const nextLabels = Object.keys(resultMatrix)
      const nextMatrix = nextLabels.map((row) => nextLabels.map((column) => Number(resultMatrix[row]?.[column] ?? 0)))
      setLabels(nextLabels)
      setMatrix(nextMatrix)
    } catch (err) {
      setError(err instanceof Error ? err.message : copy.error)
    } finally {
      setLoading(false)
    }
  }

  const option = useMemo<EChartsOption | undefined>(() => {
    if (!labels.length || !matrix.length) return undefined

    const data: [number, number, number][] = []
    for (let row = 0; row < labels.length; row += 1) {
      for (let column = 0; column < labels.length; column += 1) {
        data.push([column, row, Number((matrix[row]?.[column] ?? 0).toFixed(4))])
      }
    }

    return {
      backgroundColor: "transparent",
      tooltip: {
        position: "top",
        formatter: (params: unknown) => {
          const item = params as { data: [number, number, number] }
          const [x, y, value] = item.data
          return `<b>${labels[x]}</b> vs <b>${labels[y]}</b><br/>r = <b>${value.toFixed(4)}</b>`
        }
      },
      grid: { left: "3%", right: "8%", top: "8%", bottom: "12%", containLabel: true },
      xAxis: {
        type: "category",
        data: labels,
        axisLabel: { rotate: 30, interval: 0, fontSize: 11 }
      },
      yAxis: {
        type: "category",
        data: labels,
        axisLabel: { interval: 0, fontSize: 11 }
      },
      visualMap: {
        min: -1,
        max: 1,
        precision: 2,
        calculable: true,
        orient: "vertical",
        right: 8,
        top: "center",
        inRange: {
          color: ["#2166ac", "#4393c3", "#92c5de", "#d1e5f0", "#f7f7f7", "#fddbc7", "#f4a582", "#d6604d", "#b2182b"]
        }
      },
      series: [
        {
          name: copy.tooltipName,
          type: "heatmap",
          data,
          label: {
            show: labels.length <= 8,
            fontSize: 10,
            formatter: (params: unknown) => {
              const item = params as { value: [number, number, number] }
              return item.value[2].toFixed(2)
            }
          },
          emphasis: {
            itemStyle: { shadowBlur: 10, shadowColor: "rgba(0, 0, 0, 0.35)" }
          }
        }
      ]
    }
  }, [copy.tooltipName, labels, matrix])

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6">
      <div className="flex items-center gap-3">
        <BarChart3 className="size-6 text-primary" />
        <h1 className="text-2xl font-bold">{copy.title}</h1>
      </div>

      <section className="flex flex-col gap-4 rounded-lg border bg-card p-4">
        <div className="flex flex-col gap-1.5">
          <Label>{copy.assetCodes}</Label>
          <Input value={codes} onChange={(event) => setCodes(event.target.value)} placeholder="BTC-USDT,ETH-USDT,SPY" />
          <p className="text-xs text-muted-foreground">{copy.assetHint}</p>
        </div>

        <div className="flex flex-wrap gap-4">
          <div className="flex flex-col gap-1.5">
            <Label>{copy.window}</Label>
            <div className="flex flex-wrap gap-1.5">
              {WINDOWS.map((windowSize) => (
                <Button key={windowSize} type="button" variant={days === windowSize ? "default" : "outline"} size="sm" onClick={() => setDays(windowSize)}>
                  {windowSize}d
                </Button>
              ))}
            </div>
          </div>

          <div className="flex flex-col gap-1.5">
            <Label>{copy.method}</Label>
            <div className="flex gap-1.5">
              {METHODS.map((item) => (
                <Button key={item} type="button" variant={method === item ? "default" : "outline"} size="sm" className="capitalize" onClick={() => setMethod(item)}>
                  {item}
                </Button>
              ))}
            </div>
          </div>
        </div>

        <Button className="self-start" onClick={compute} disabled={loading}>
          {loading ? copy.loading : copy.compute}
        </Button>
      </section>

      {error ? <div className="rounded-md border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive">{error}</div> : null}

      <EChartPanel option={option} loading={loading} empty={!option} emptyText={copy.noData} height={520} />
    </div>
  )
}
