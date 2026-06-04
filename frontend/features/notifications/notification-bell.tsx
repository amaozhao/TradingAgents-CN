"use client"

import { useEffect } from "react"
import { Bell } from "lucide-react"

import { Button } from "@/components/ui/button"
import { NotificationDrawer } from "@/features/notifications/notification-drawer"
import { useAuthStore } from "@/stores/auth-store"
import { useNotificationStore } from "@/stores/notification-store"

export function NotificationBell() {
  const token = useAuthStore((state) => state.token)
  const unreadCount = useNotificationStore((state) => state.unreadCount)
  const setDrawerVisible = useNotificationStore((state) => state.setDrawerVisible)
  const refreshUnreadCount = useNotificationStore((state) => state.refreshUnreadCount)
  const connectWebSocket = useNotificationStore((state) => state.connectWebSocket)
  const disconnectWebSocket = useNotificationStore((state) => state.disconnectWebSocket)

  useEffect(() => {
    if (!token) {
      disconnectWebSocket()
      return
    }

    void refreshUnreadCount()
    connectWebSocket()

    const timer = window.setInterval(() => {
      void refreshUnreadCount()
    }, 30000)

    return () => {
      window.clearInterval(timer)
      disconnectWebSocket()
    }
  }, [connectWebSocket, disconnectWebSocket, refreshUnreadCount, token])

  const displayCount = unreadCount > 99 ? "99+" : String(unreadCount)

  return (
    <>
      <Button
        variant="ghost"
        size="icon"
        aria-label={unreadCount > 0 ? `通知，${unreadCount} 条未读` : "通知"}
        className="relative"
        onClick={() => setDrawerVisible(true)}
      >
        <Bell />
        {unreadCount > 0 ? (
          <span className="absolute -right-0.5 -top-0.5 flex h-5 min-w-[1.25rem] items-center justify-center rounded-full bg-destructive px-1 text-[10px] font-semibold leading-none text-destructive-foreground">
            {displayCount}
          </span>
        ) : null}
      </Button>
      <NotificationDrawer />
    </>
  )
}
