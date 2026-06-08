import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import type { ResearchSession } from "@/libs/api/research-agent"

const defaultSessions = [
  { session_id: "session-storage", title: "储能产业链研究", status: "active" },
  { session_id: "session-baijiu", title: "白酒估值复盘", status: "archived" }
]

export function SessionSidebar({ sessions = defaultSessions }: { sessions?: Array<ResearchSession & { status?: string }> }) {
  return (
    <section className="rounded-lg border bg-card p-4">
      <div className="mb-3 flex items-center justify-between gap-2">
        <h2 className="text-base font-semibold">会话列表</h2>
        <Button size="sm">新建</Button>
      </div>
      <div className="space-y-2">
        {sessions.map((session) => (
          <button key={session.session_id} className="w-full rounded-md border px-3 py-2 text-left text-sm hover:bg-muted">
            <div className="flex items-center justify-between gap-2">
              <span className="font-medium">{session.title}</span>
              <Badge variant={session.status === "active" ? "default" : "secondary"}>{session.status}</Badge>
            </div>
            <p className="mt-1 text-xs text-muted-foreground">{session.session_id}</p>
          </button>
        ))}
      </div>
    </section>
  )
}
