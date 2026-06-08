import { CheckCircle2, Clock3 } from "lucide-react"

export interface ResearchToolTimelineItem {
  id: string
  name: string
  status: string
  artifactId?: string
}

const defaultTools: ResearchToolTimelineItem[] = [
  { id: "screening_run", name: "screening_run", status: "completed" },
  { id: "alpha_bench", name: "alpha_bench", status: "completed" },
  { id: "correlation_matrix", name: "correlation_matrix", status: "running" }
]

export function ToolTimeline({ tools = defaultTools }: { tools?: ResearchToolTimelineItem[] }) {
  return (
    <section aria-label="工具时间线" className="rounded-lg border bg-card p-4">
      <h2 className="mb-3 text-base font-semibold">工具时间线</h2>
      <div className="space-y-2">
        {tools.map((tool) => {
          const Icon = tool.status === "completed" ? CheckCircle2 : Clock3
          return (
            <div key={tool.id} className="flex items-center justify-between rounded-md border px-3 py-2 text-sm">
              <span>
                <span className="font-medium">{tool.name}</span>
                {tool.artifactId ? (
                  <span className="ml-2 text-xs text-muted-foreground">{tool.artifactId}</span>
                ) : null}
              </span>
              <span className="flex items-center gap-2 text-muted-foreground">
                <Icon className="size-4" />
                {tool.status}
              </span>
            </div>
          )
        })}
      </div>
    </section>
  )
}
