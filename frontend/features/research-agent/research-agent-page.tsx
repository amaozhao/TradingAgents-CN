"use client"

import { Bot, RefreshCw, Square } from "lucide-react"

import { PageHeader } from "@/components/feedback/page-header"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { ArtifactDrawer } from "@/features/research-agent/artifact-drawer"
import { MessageTimeline } from "@/features/research-agent/message-timeline"
import { SessionSidebar } from "@/features/research-agent/session-sidebar"
import { ToolTimeline } from "@/features/research-agent/tool-timeline"

export function ResearchAgentPage() {
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
        <SessionSidebar />
        <div className="space-y-4">
          <Card>
            <CardHeader className="flex-row items-center justify-between">
              <CardTitle className="flex items-center gap-2 text-base"><Bot className="size-4" />当前研究</CardTitle>
              <span className="text-sm text-muted-foreground">model: MiniMax-M3 · running</span>
            </CardHeader>
            <CardContent>
              <MessageTimeline />
            </CardContent>
          </Card>
          <ToolTimeline />
          <Card>
            <CardHeader><CardTitle className="text-base">最终报告</CardTitle></CardHeader>
            <CardContent className="text-sm text-muted-foreground">
              等待 Agent 汇总证据、风险因素、候选股票和最终交易决策。
            </CardContent>
          </Card>
        </div>
        <ArtifactDrawer />
      </div>
    </div>
  )
}
