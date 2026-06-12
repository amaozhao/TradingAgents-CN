"use client"

import { ArrowDown, Bot, Loader2 } from "lucide-react"

import { AGENT_TEXT } from "@/features/agent/text"

type AgentText = typeof AGENT_TEXT[keyof typeof AGENT_TEXT]

export function RunningIndicator({ text }: { text: AgentText }) {
  return (
    <div className="flex gap-3">
      <div className="mt-1 flex size-8 shrink-0 items-center justify-center rounded-full border bg-background">
        <Bot className="size-4 text-primary" />
      </div>
      <div className="flex min-w-0 flex-1 items-center gap-2 pt-2 text-sm text-muted-foreground">
        <Loader2 className="size-4 animate-spin text-primary" />
        <span>{text.working}</span>
      </div>
    </div>
  )
}

export function ScrollButton({ text, onClick }: { text: AgentText; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="sticky bottom-4 left-1/2 z-10 flex -translate-x-1/2 items-center gap-1 rounded-full bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground shadow-lg"
    >
      <ArrowDown className="size-3" />{text.newMessages}
    </button>
  )
}
