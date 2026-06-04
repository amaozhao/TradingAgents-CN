"use client"

import { useEffect, useId, useState } from "react"
import { useTheme } from "next-themes"

import { ErrorState } from "@/components/feedback/error-state"
import { cn } from "@/libs/utils"

interface MermaidRendererProps {
  chart: string
  className?: string
}

export function MermaidRenderer({ chart, className }: MermaidRendererProps) {
  const id = useId().replace(/[^a-zA-Z0-9_-]/g, "")
  const { resolvedTheme } = useTheme()
  const [svg, setSvg] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false

    async function renderChart() {
      try {
        const mermaid = (await import("mermaid")).default
        mermaid.initialize({
          startOnLoad: false,
          theme: resolvedTheme === "dark" ? "dark" : "default",
          securityLevel: "strict"
        })
        const result = await mermaid.render(`mermaid-${id}`, chart)

        if (!cancelled) {
          setSvg(result.svg)
          setError(null)
        }
      } catch (caught) {
        if (!cancelled) {
          setSvg(null)
          setError(caught instanceof Error ? caught.message : "Mermaid 渲染失败")
        }
      }
    }

    renderChart()

    return () => {
      cancelled = true
    }
  }, [chart, id, resolvedTheme])

  if (error) {
    return <ErrorState title="图表渲染失败" description={error} className={className} />
  }

  return (
    <div
      className={cn("overflow-x-auto rounded-md border bg-background p-4", className)}
      dangerouslySetInnerHTML={{ __html: svg ?? "" }}
    />
  )
}
