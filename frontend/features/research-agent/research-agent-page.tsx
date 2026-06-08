"use client"

import { useEffect, useMemo, useState } from "react"
import { Bot, RefreshCw, Send, Square } from "lucide-react"

import { PageHeader } from "@/components/feedback/page-header"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { ArtifactDrawer } from "@/features/research-agent/artifact-drawer"
import { MessageTimeline, type ResearchTimelineMessage } from "@/features/research-agent/message-timeline"
import { SessionSidebar } from "@/features/research-agent/session-sidebar"
import { ToolTimeline, type ResearchToolTimelineItem } from "@/features/research-agent/tool-timeline"
import { researchAgentApi, type ResearchSession } from "@/libs/api/research-agent"

const FINAL_REPORT_STORAGE_KEY = "research-agent-final-report"

function readStoredFinalReport() {
  if (typeof window === "undefined") return ""
  return window.localStorage.getItem(FINAL_REPORT_STORAGE_KEY) || ""
}

function eventContent(data: Record<string, unknown>) {
  return String(data.content || data.text || "")
}

export function ResearchAgentPage() {
  const [sessions, setSessions] = useState<ResearchSession[]>([])
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null)
  const [messages, setMessages] = useState<ResearchTimelineMessage[]>([])
  const [tools, setTools] = useState<ResearchToolTimelineItem[]>([])
  const [finalReport, setFinalReport] = useState(readStoredFinalReport)
  const [prompt, setPrompt] = useState("")
  const [status, setStatus] = useState<"idle" | "running" | "completed">(
    () => (readStoredFinalReport() ? "completed" : "idle")
  )

  useEffect(() => {
    void researchAgentApi.listSessions().then((response) => {
      const loadedSessions = response.data || []
      setSessions(loadedSessions)
      if (loadedSessions[0]?.session_id) {
        setActiveSessionId(loadedSessions[0].session_id)
      }
    }).catch(() => {
      setSessions([])
    })
  }, [])

  const artifacts = useMemo(
    () =>
      tools
        .filter((tool) => tool.artifactId)
        .map((tool) => ({ id: String(tool.artifactId), type: tool.name })),
    [tools]
  )

  async function ensureSession() {
    if (activeSessionId) return activeSessionId

    const response = await researchAgentApi.createSession({ title: "储能板块分析" })
    const session = response.data
    setActiveSessionId(session.session_id)
    setSessions((current) => [session, ...current])
    return session.session_id
  }

  async function onSubmit() {
    const content = prompt.trim()
    if (!content) return

    setStatus("running")
    setFinalReport("")
    window.localStorage.removeItem(FINAL_REPORT_STORAGE_KEY)
    setMessages([{ id: `user-${Date.now()}`, role: "user", content }])
    setTools([])

    const sessionId = await ensureSession()
    await researchAgentApi.appendMessage(sessionId, {
      role: "user",
      content,
      metadata: { source: "agent-page" }
    })
    setPrompt("")

    const events = await researchAgentApi.streamEvents(sessionId)
    for (const item of events) {
      if (item.event === "assistant_delta") {
        const delta = eventContent(item.data)
        if (delta) {
          setMessages((current) => [
            ...current,
            { id: `assistant-${current.length}-${Date.now()}`, role: "assistant", content: delta }
          ])
        }
      }

      if (item.event === "tool_completed") {
        const toolName = String(item.data.tool_name || "tool")
        const artifactId = item.data.artifact_id ? String(item.data.artifact_id) : undefined
        setTools((current) => [
          ...current,
          {
            id: `${toolName}-${current.length}`,
            name: toolName,
            status: "completed",
            artifactId
          }
        ])
      }

      if (item.event === "message_completed") {
        const report = eventContent(item.data)
        if (report) {
          setFinalReport(report)
          window.localStorage.setItem(FINAL_REPORT_STORAGE_KEY, report)
        }
        setStatus("completed")
      }
    }
  }

  return (
    <div>
      <PageHeader
        title="研究 Agent"
        description="面向单股、行业、Alpha 和矩阵产物的持久化研究工作台"
        actions={
          <>
            <Button variant="outline"><Square className="mr-2 size-4" />取消</Button>
            <Button variant="outline"><RefreshCw className="mr-2 size-4" />重试</Button>
          </>
        }
      />
      <div className="grid gap-4 lg:grid-cols-[280px_minmax(0,1fr)_320px]">
        <SessionSidebar sessions={sessions.map((session) => ({ ...session, status: "active" }))} />
        <div className="space-y-4">
          <Card>
            <CardHeader className="flex-row items-center justify-between">
              <CardTitle className="flex items-center gap-2 text-base"><Bot className="size-4" />当前研究</CardTitle>
              <span className="text-sm text-muted-foreground">model: MiniMax-M3 · {status}</span>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <label htmlFor="research-agent-prompt" className="text-sm font-medium">研究提示</label>
                <textarea
                  id="research-agent-prompt"
                  className="min-h-24 w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm shadow-sm outline-none focus-visible:ring-1 focus-visible:ring-ring"
                  value={prompt}
                  onChange={(event) => setPrompt(event.target.value)}
                  placeholder="输入行业、股票池、因子或组合研究问题"
                />
                <div className="flex justify-end">
                  <Button onClick={onSubmit} disabled={status === "running" || !prompt.trim()}>
                    <Send className="mr-2 size-4" />发送
                  </Button>
                </div>
              </div>
              <MessageTimeline messages={messages.length ? messages : undefined} />
            </CardContent>
          </Card>
          <ToolTimeline tools={tools.length ? tools : undefined} />
          <section aria-label="最终报告">
          <Card>
            <CardHeader><CardTitle className="text-base">最终报告</CardTitle></CardHeader>
            <CardContent className="text-sm text-muted-foreground">
              {finalReport || "等待 Agent 汇总证据、风险因素、候选股票和最终交易决策。"}
            </CardContent>
          </Card>
          </section>
        </div>
        <ArtifactDrawer artifacts={artifacts.length ? artifacts : undefined} />
      </div>
    </div>
  )
}
