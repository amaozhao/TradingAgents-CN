import { CheckCircle2, Clock3 } from "lucide-react"

const tools = [
  { name: "screening_run", status: "completed" },
  { name: "alpha_bench", status: "completed" },
  { name: "correlation_matrix", status: "running" }
]

export function ToolTimeline() {
  return (
    <section className="rounded-lg border bg-card p-4">
      <h2 className="mb-3 text-base font-semibold">工具时间线</h2>
      <div className="space-y-2">
        {tools.map((tool) => {
          const Icon = tool.status === "completed" ? CheckCircle2 : Clock3
          return (
            <div key={tool.name} className="flex items-center justify-between rounded-md border px-3 py-2 text-sm">
              <span className="font-medium">{tool.name}</span>
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
