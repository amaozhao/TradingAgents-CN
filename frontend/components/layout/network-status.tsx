"use client"

import { AlertTriangle, RefreshCw, WifiOff } from "lucide-react"
import { useState } from "react"

import { Button } from "@/components/ui/button"
import { testApiConnection } from "@/libs/api/request"
import { useAppStore } from "@/stores/app-store"

export function NetworkStatus() {
  const isOnline = useAppStore((state) => state.isOnline)
  const apiConnected = useAppStore((state) => state.apiConnected)
  const checkApiConnection = useAppStore((state) => state.checkApiConnection)
  const [retrying, setRetrying] = useState(false)

  if (isOnline && apiConnected) {
    return null
  }

  const title = !isOnline ? "网络连接已断开" : "后端服务连接失败"
  const Icon = !isOnline ? WifiOff : AlertTriangle

  return (
    <div className="fixed right-4 top-4 z-50 flex max-w-md items-center gap-3 rounded-md border bg-background px-4 py-3 text-sm shadow-lg">
      <Icon className="size-5 text-destructive" />
      <div className="min-w-0 flex-1">
        <div className="font-medium">{title}</div>
        <div className="text-muted-foreground">
          {!isOnline ? "请检查您的网络连接" : "无法连接到后端服务，请检查服务是否正常运行"}
        </div>
      </div>
      {isOnline ? (
        <Button
          size="sm"
          variant="outline"
          disabled={retrying}
          onClick={async () => {
            setRetrying(true)
            try {
              await checkApiConnection(testApiConnection)
            } finally {
              setRetrying(false)
            }
          }}
        >
          <RefreshCw className={retrying ? "size-4 animate-spin" : "size-4"} />
          重试
        </Button>
      ) : null}
    </div>
  )
}
