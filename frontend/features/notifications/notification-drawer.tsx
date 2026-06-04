"use client"

import { useEffect, useState } from "react"
import { CheckCheck, ExternalLink } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle
} from "@/components/ui/sheet"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { formatDateTime } from "@/libs/utils/datetime"
import { useNotificationStore, type NotificationItem } from "@/stores/notification-store"

const typeLabels: Record<string, string> = {
  analysis: "分析",
  alert: "预警",
  system: "系统"
}

function notificationTypeLabel(type: string) {
  return typeLabels[type] || type
}

function notificationBadgeVariant(type: string) {
  if (type === "alert") return "destructive"
  if (type === "system") return "secondary"
  return "default"
}

function EmptyNotifications({ loading }: { loading: boolean }) {
  return (
    <div className="flex h-48 items-center justify-center rounded-md border border-dashed text-sm text-muted-foreground">
      {loading ? "正在加载通知..." : "暂无通知"}
    </div>
  )
}

function NotificationRow({ item }: { item: NotificationItem }) {
  const markRead = useNotificationStore((state) => state.markRead)

  const handleOpen = async () => {
    if (item.status === "unread") {
      await markRead(item.id)
    }
    if (item.link) {
      window.open(item.link, "_blank", "noopener,noreferrer")
    }
  }

  return (
    <div className="rounded-md border bg-card p-3">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 space-y-1">
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant={notificationBadgeVariant(item.type)}>{notificationTypeLabel(item.type)}</Badge>
            {item.status === "unread" ? <Badge variant="outline">未读</Badge> : null}
            <span className="text-xs text-muted-foreground">{formatDateTime(item.created_at)}</span>
          </div>
          <div className="break-words text-sm font-medium">{item.title}</div>
        </div>
      </div>
      {item.content ? (
        <p className="mt-2 break-words text-sm leading-6 text-muted-foreground">{item.content}</p>
      ) : null}
      <div className="mt-3 flex items-center justify-end gap-2">
        {item.link ? (
          <Button variant="outline" size="sm" onClick={handleOpen}>
            <ExternalLink className="mr-2 h-4 w-4" />
            查看
          </Button>
        ) : null}
        {item.status === "unread" ? (
          <Button variant="ghost" size="sm" onClick={() => markRead(item.id)}>
            标记已读
          </Button>
        ) : null}
      </div>
    </div>
  )
}

export function NotificationDrawer() {
  const [status, setStatus] = useState<"all" | "unread">("all")
  const drawerVisible = useNotificationStore((state) => state.drawerVisible)
  const setDrawerVisible = useNotificationStore((state) => state.setDrawerVisible)
  const items = useNotificationStore((state) => state.items)
  const unreadCount = useNotificationStore((state) => state.unreadCount)
  const loading = useNotificationStore((state) => state.loading)
  const loadList = useNotificationStore((state) => state.loadList)
  const markAllRead = useNotificationStore((state) => state.markAllRead)

  useEffect(() => {
    if (!drawerVisible) return

    void loadList(status)
    const timer = window.setInterval(() => {
      void loadList(status)
    }, 60000)

    return () => window.clearInterval(timer)
  }, [drawerVisible, loadList, status])

  return (
    <Sheet open={drawerVisible} onOpenChange={setDrawerVisible}>
      <SheetContent className="flex w-full flex-col p-0 sm:max-w-[430px]">
        <SheetHeader className="border-b px-5 py-4">
          <SheetTitle>消息中心</SheetTitle>
          <SheetDescription>未读 {unreadCount} 条</SheetDescription>
        </SheetHeader>

        <div className="flex items-center justify-between gap-3 border-b px-5 py-3">
          <Tabs value={status} onValueChange={(value) => setStatus(value as "all" | "unread")}>
            <TabsList>
              <TabsTrigger value="all">全部</TabsTrigger>
              <TabsTrigger value="unread">未读</TabsTrigger>
            </TabsList>
          </Tabs>
          <Button variant="outline" size="sm" disabled={loading || unreadCount === 0} onClick={() => markAllRead()}>
            <CheckCheck className="mr-2 h-4 w-4" />
            全部已读
          </Button>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4">
          {items.length === 0 ? (
            <EmptyNotifications loading={loading} />
          ) : (
            <div className="space-y-3">
              {items.map((item) => (
                <NotificationRow key={item.id} item={item} />
              ))}
            </div>
          )}
        </div>
      </SheetContent>
    </Sheet>
  )
}
