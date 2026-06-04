"use client"

import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { MarkdownRenderer } from "@/features/learning/markdown-renderer"

export function TaskReportDialog({
  open,
  title = "任务报告",
  content,
  onOpenChange
}: {
  open: boolean
  title?: string
  content?: string
  onOpenChange: (open: boolean) => void
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl">
        <DialogHeader><DialogTitle>{title}</DialogTitle></DialogHeader>
        <MarkdownRenderer content={content || "暂无报告内容"} />
      </DialogContent>
    </Dialog>
  )
}
