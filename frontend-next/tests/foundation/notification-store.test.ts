import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

const apiMocks = vi.hoisted(() => ({
  getUnreadCount: vi.fn(),
  getList: vi.fn(),
  markRead: vi.fn(),
  markAllRead: vi.fn()
}))

vi.mock("@/libs/api/notifications", () => ({
  notificationsApi: apiMocks
}))

import { resetAuthStoreForTests, useAuthStore } from "@/stores/auth-store"
import { resetNotificationStoreForTests, useNotificationStore } from "@/stores/notification-store"

class MockWebSocket {
  static instances: MockWebSocket[] = []

  url: string
  onopen: ((event: Event) => void) | null = null
  onclose: ((event: CloseEvent) => void) | null = null
  onerror: ((event: Event) => void) | null = null
  onmessage: ((event: MessageEvent) => void) | null = null
  close = vi.fn()

  constructor(url: string) {
    this.url = url
    MockWebSocket.instances.push(this)
  }

  emitOpen() {
    this.onopen?.(new Event("open"))
  }

  emitMessage(data: unknown) {
    this.onmessage?.({ data: JSON.stringify(data) } as MessageEvent)
  }
}

describe("notification store", () => {
  beforeEach(() => {
    resetAuthStoreForTests()
    resetNotificationStoreForTests()
    MockWebSocket.instances = []
    apiMocks.getUnreadCount.mockResolvedValue({ success: true, data: { count: 3 } })
    apiMocks.getList.mockResolvedValue({
      success: true,
      data: {
        items: [
          {
            id: "n1",
            title: "分析完成",
            type: "analysis",
            status: "unread",
            created_at: "2026-06-04T10:00:00.000Z"
          }
        ],
        total: 1
      }
    })
    apiMocks.markRead.mockResolvedValue({ success: true })
    apiMocks.markAllRead.mockResolvedValue({ success: true })
    vi.stubGlobal("WebSocket", MockWebSocket)
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    vi.clearAllMocks()
  })

  it("inserts notifications and keeps unread counts idempotent", () => {
    const store = useNotificationStore.getState()

    store.addNotification({ id: "n1", title: "分析完成", type: "analysis" })
    store.addNotification({ id: "n2", title: "系统通知", type: "system", status: "read" })

    expect(useNotificationStore.getState().items.map((item) => item.id)).toEqual(["n2", "n1"])
    expect(useNotificationStore.getState().unreadCount).toBe(1)

    useNotificationStore.getState().markReadLocal("n1")
    useNotificationStore.getState().markReadLocal("n1")

    expect(useNotificationStore.getState().unreadCount).toBe(0)
    expect(useNotificationStore.getState().items[1].status).toBe("read")

    useNotificationStore.getState().addNotification({ id: "n3", title: "预警", type: "alert" })
    useNotificationStore.getState().markAllReadLocal()

    expect(useNotificationStore.getState().items.every((item) => item.status === "read")).toBe(true)
    expect(useNotificationStore.getState().unreadCount).toBe(0)
  })

  it("syncs unread counts and list state through the notifications API", async () => {
    await useNotificationStore.getState().refreshUnreadCount()
    expect(useNotificationStore.getState().unreadCount).toBe(3)

    await useNotificationStore.getState().loadList("unread")
    expect(apiMocks.getList).toHaveBeenCalledWith({ status: "unread", page: 1, page_size: 20 })
    expect(useNotificationStore.getState().items).toHaveLength(1)
    expect(useNotificationStore.getState().loading).toBe(false)

    await useNotificationStore.getState().markRead("n1")
    expect(apiMocks.markRead).toHaveBeenCalledWith("n1")
    expect(apiMocks.getUnreadCount).toHaveBeenCalledTimes(2)

    await useNotificationStore.getState().markAllRead()
    expect(apiMocks.markAllRead).toHaveBeenCalledTimes(1)
    expect(apiMocks.getUnreadCount).toHaveBeenCalledTimes(3)
  })

  it("connects to the authenticated notification websocket and inserts frames", () => {
    useAuthStore.getState().setAuthInfo("access.token", null, { username: "admin" })

    useNotificationStore.getState().connectWebSocket()

    expect(MockWebSocket.instances).toHaveLength(1)
    expect(MockWebSocket.instances[0].url).toContain("/api/ws/notifications?token=access.token")

    MockWebSocket.instances[0].emitOpen()
    expect(useNotificationStore.getState().wsConnected).toBe(true)

    MockWebSocket.instances[0].emitMessage({
      type: "notification",
      data: {
        id: "ws-1",
        title: "任务完成",
        type: "analysis",
        content: "AAPL 分析完成"
      }
    })

    expect(useNotificationStore.getState().items[0]).toMatchObject({
      id: "ws-1",
      title: "任务完成",
      status: "unread"
    })
    expect(useNotificationStore.getState().unreadCount).toBe(1)

    useNotificationStore.getState().disconnectWebSocket()

    expect(MockWebSocket.instances[0].close).toHaveBeenCalledTimes(1)
    expect(useNotificationStore.getState().ws).toBeNull()
    expect(useNotificationStore.getState().wsConnected).toBe(false)
  })
})
