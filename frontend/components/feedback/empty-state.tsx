import { Inbox } from "lucide-react"

import { cn } from "@/libs/utils"

interface EmptyStateProps {
  title?: string
  description?: string
  className?: string
}

export function EmptyState({
  title = "暂无数据",
  description = "当前没有可展示的内容。",
  className
}: EmptyStateProps) {
  return (
    <div className={cn("flex flex-col items-center justify-center gap-3 py-10 text-center", className)}>
      <Inbox className="size-8 text-muted-foreground" aria-hidden="true" />
      <div className="space-y-1">
        <h3 className="text-sm font-medium">{title}</h3>
        <p className="text-sm text-muted-foreground">{description}</p>
      </div>
    </div>
  )
}
