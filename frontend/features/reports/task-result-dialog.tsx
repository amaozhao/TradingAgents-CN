"use client"

import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog"

export function TaskResultDialog({
  open,
  result,
  onOpenChange
}: {
  open: boolean
  result?: unknown
  onOpenChange: (open: boolean) => void
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl">
        <DialogHeader><DialogTitle>任务结果</DialogTitle></DialogHeader>
        <pre className="max-h-[60vh] overflow-auto rounded-md bg-muted p-4 text-sm">
          {JSON.stringify(result ?? {}, null, 2)}
        </pre>
      </DialogContent>
    </Dialog>
  )
}
