"use client"

import { Bot, Download, Plus } from "lucide-react"

import { Button } from "@/components/ui/button"
import { AGENT_TEXT } from "@/features/agent/text"
import type { ResearchGoal } from "@/libs/api/research-agent"

type AgentText = typeof AGENT_TEXT[keyof typeof AGENT_TEXT]

export function AgentHeader({
  cancelRequested,
  goal,
  messagesLength,
  running,
  text,
  onExport,
  onNew
}: {
  cancelRequested: boolean
  goal: ResearchGoal | null
  messagesLength: number
  running: boolean
  text: AgentText
  onExport: () => void
  onNew: () => void
}) {
  const statusLabel = cancelRequested ? text.cancelling : running ? text.running : text.ready

  return (
    <header className="flex items-center justify-between gap-3 border-b px-4 py-3">
      <div className="min-w-0">
        <div className="flex items-center gap-2">
          <Bot className="size-5 text-primary" />
          <h1 className="truncate text-base font-semibold">{text.pageTitle}</h1>
          <span className="rounded-full border px-2 py-0.5 text-[11px] text-muted-foreground">{statusLabel}</span>
        </div>
        <p className="mt-1 truncate text-xs text-muted-foreground">
          {text.pageSubtitle}
        </p>
      </div>
      <div className="flex shrink-0 items-center gap-2">
        <Button variant="outline" size="sm" onClick={onNew}>
          <Plus className="mr-2 size-4" />{text.newSession}
        </Button>
        {(messagesLength > 0 || goal) && (
          <Button variant="outline" size="sm" onClick={onExport}>
            <Download className="mr-2 size-4" />{text.exportChat}
          </Button>
        )}
      </div>
    </header>
  )
}
