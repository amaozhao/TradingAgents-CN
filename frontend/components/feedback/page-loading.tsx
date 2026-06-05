import { Loader2 } from "lucide-react"

import { Skeleton } from "@/components/ui/skeleton"
import { cn } from "@/libs/utils"

interface PageLoadingProps {
  className?: string
}

export function PageLoading({ className }: PageLoadingProps) {
  return (
    <main
      className={cn(
        "min-h-[calc(100vh-4rem)] bg-background px-4 py-6 sm:px-6 lg:px-8",
        className
      )}
      aria-busy="true"
      aria-live="polite"
      aria-label="页面加载中"
    >
      <div className="mx-auto flex w-full max-w-7xl flex-col gap-6">
        <div className="flex items-center gap-3">
          <span className="flex size-10 items-center justify-center rounded-md border bg-card text-primary shadow-sm">
            <Loader2 className="size-5 animate-spin" aria-hidden="true" />
          </span>
          <div className="space-y-2">
            <Skeleton className="h-4 w-32" />
            <Skeleton className="h-3 w-56" />
          </div>
        </div>

        <div className="grid gap-4 md:grid-cols-3">
          <Skeleton className="h-24" />
          <Skeleton className="h-24" />
          <Skeleton className="h-24" />
        </div>

        <div className="rounded-md border bg-card p-4 shadow-sm">
          <div className="space-y-3">
            <Skeleton className="h-4 w-40" />
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-10 w-5/6" />
          </div>
        </div>
      </div>
    </main>
  )
}
