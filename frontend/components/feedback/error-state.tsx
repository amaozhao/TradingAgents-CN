import { AlertCircle } from "lucide-react"

import { Button } from "@/components/ui/button"
import { cn } from "@/libs/utils"

interface ErrorStateProps {
  title?: string
  description?: string
  actionLabel?: string
  onAction?: () => void
  className?: string
}

export function ErrorState({
  title = "加载失败",
  description = "请求未能完成，请稍后重试。",
  actionLabel,
  onAction,
  className
}: ErrorStateProps) {
  return (
    <div className={cn("flex flex-col items-center justify-center gap-3 py-10 text-center", className)}>
      <AlertCircle className="size-8 text-destructive" aria-hidden="true" />
      <div className="space-y-1">
        <h3 className="text-sm font-medium">{title}</h3>
        <p className="text-sm text-muted-foreground">{description}</p>
      </div>
      {actionLabel && onAction ? (
        <Button variant="outline" size="sm" onClick={onAction}>
          {actionLabel}
        </Button>
      ) : null}
    </div>
  )
}
