"use client"

import type { FormEvent, KeyboardEvent, RefObject } from "react"
import { BarChart3, Plus, Send, Sparkles, Square, Target, TrendingUp, X } from "lucide-react"

import { Button } from "@/components/ui/button"
import { AGENT_TEXT } from "@/features/agent/text"

type AgentText = typeof AGENT_TEXT[keyof typeof AGENT_TEXT]

export function AgentComposer({
  composerMode,
  composerRef,
  input,
  menuRef,
  running,
  showMenu,
  text,
  fillComposerFromQuickPrompt,
  handleCancel,
  handleComposerKeyDown,
  handleSubmit,
  onOpenBatchConfig,
  onOpenStockConfig,
  setComposerMode,
  setInput,
  setShowMenu
}: {
  composerMode: "chat" | "goal"
  composerRef: RefObject<HTMLTextAreaElement | null>
  input: string
  menuRef: RefObject<HTMLDivElement | null>
  running: boolean
  showMenu: boolean
  text: AgentText
  fillComposerFromQuickPrompt: (prompt: string) => void
  handleCancel: () => void
  handleComposerKeyDown: (event: KeyboardEvent<HTMLTextAreaElement>) => void
  handleSubmit: (event: FormEvent) => void
  onOpenBatchConfig: () => void
  onOpenStockConfig: () => void
  setComposerMode: (mode: "chat" | "goal") => void
  setInput: (value: string) => void
  setShowMenu: (value: boolean | ((open: boolean) => boolean)) => void
}) {
  return (
    <form onSubmit={handleSubmit} className="min-w-0 border-t bg-background/90 p-4">
      <div className="w-full min-w-0 space-y-2">
        <div className="flex flex-wrap items-center gap-2">
          {composerMode === "goal" && (
            <span className="inline-flex items-center gap-1 rounded-lg bg-primary/10 px-2.5 py-1 text-xs font-medium text-primary">
              <Target className="size-3" />{text.goalModeChip}
              <button type="button" onClick={() => setComposerMode("chat")}><X className="size-3" /></button>
            </span>
          )}
        </div>
        <div className="flex min-w-0 items-center gap-2">
          <div ref={menuRef} className="relative">
            <Button type="button" variant="outline" size="icon" disabled={running} onClick={() => setShowMenu((open) => !open)} aria-label={text.moreOptions} className="size-11 rounded-xl">
              <Plus className="size-4" />
            </Button>
            {showMenu && (
              <div className="absolute bottom-full left-0 z-20 mb-2 w-56 rounded-lg border bg-background py-1 shadow-lg">
                <button type="button" onClick={() => { setComposerMode("goal"); setShowMenu(false) }} className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm hover:bg-muted">
                  <Target className="size-4" />{text.researchGoal}
                </button>
                <button
                  type="button"
                  disabled={running}
                  onClick={onOpenStockConfig}
                  className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm hover:bg-muted disabled:cursor-not-allowed disabled:opacity-50"
                >
                  <TrendingUp className="size-4" />{text.singleStock}
                </button>
                <button
                  type="button"
                  disabled={running}
                  onClick={onOpenBatchConfig}
                  className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm hover:bg-muted disabled:cursor-not-allowed disabled:opacity-50"
                >
                  <BarChart3 className="size-4" />{text.batchStock}
                </button>
                <div className="my-1 border-t" />
                {text.quickPrompts.map((item) => {
                  const Icon = item.icon || Sparkles
                  return (
                    <button key={item.label} type="button" onClick={() => fillComposerFromQuickPrompt(item.prompt)} className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm hover:bg-muted">
                      <Icon className="size-4" />{item.label}
                    </button>
                  )
                })}
              </div>
            )}
          </div>
          <textarea
            ref={composerRef}
            value={input}
            rows={1}
            onChange={(event) => setInput(event.target.value)}
            onKeyDown={handleComposerKeyDown}
            placeholder={composerMode === "goal" ? text.goalPlaceholder : text.chatPlaceholder}
            className="max-h-32 min-h-11 min-w-0 flex-1 resize-none overflow-hidden rounded-xl border bg-background px-4 py-2.5 text-sm leading-6 outline-none transition-shadow focus:ring-2 focus:ring-primary/30"
            disabled={running}
          />
          {running ? (
            <Button type="button" variant="destructive" onClick={handleCancel} aria-label={text.stop} className="h-11 w-14 rounded-xl">
              <Square className="size-4" />
            </Button>
          ) : (
            <Button type="submit" disabled={!input.trim()} aria-label={text.send} className="h-11 w-14 rounded-xl">
              <Send className="size-4" />
            </Button>
          )}
        </div>
      </div>
    </form>
  )
}
