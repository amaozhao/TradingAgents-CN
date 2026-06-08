import { Badge } from "@/components/ui/badge"

const messages = [
  { role: "user", content: "分析储能产业链里估值和资金面更健康的公司" },
  { role: "assistant", content: "已读取筛选结果、单股分析和 Alpha artifact，正在汇总证据。" }
]

export function MessageTimeline() {
  return (
    <section className="rounded-lg border bg-card p-4">
      <h2 className="mb-3 text-base font-semibold">消息时间线</h2>
      <div className="space-y-3">
        {messages.map((message) => (
          <div key={message.role} className="rounded-md border p-3">
            <Badge variant={message.role === "user" ? "secondary" : "default"}>{message.role}</Badge>
            <p className="mt-2 text-sm">{message.content}</p>
          </div>
        ))}
      </div>
    </section>
  )
}
