"use client"

import { create } from "zustand"

import { notificationsApi } from "@/libs/api/notifications"
import { useAuthStore } from "@/stores/auth-store"

export interface NotificationItem {
  id: string
  title: string
  content?: string
  type: string
  status: "unread" | "read"
  created_at: string
  link?: string
  source?: string
}

interface NotificationState {
  items: NotificationItem[]
  unreadCount: number
  loading: boolean
  drawerVisible: boolean
  ws: WebSocket | null
  wsConnected: boolean
  wsReconnectAttempts: number
  addNotification: (notification: Partial<NotificationItem> & Pick<NotificationItem, "title" | "type">) => void
  setDrawerVisible: (visible: boolean) => void
  refreshUnreadCount: () => Promise<void>
  loadList: (status?: "unread" | "all") => Promise<void>
  markRead: (id: string) => Promise<void>
  markAllRead: () => Promise<void>
  connectWebSocket: () => void
  disconnectWebSocket: () => void
  connect: () => void
  disconnect: () => void
  markReadLocal: (id: string) => void
  markAllReadLocal: () => void
}

let reconnectTimer: ReturnType<typeof setTimeout> | null = null
let manualDisconnect = false
const maxReconnectAttempts = 10
const websocketConnectingState = 0
const websocketOpenState = 1

function getNotificationWebSocketUrl(token: string) {
  const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL
  const isLocalFrontend = ["3000", "5173"].includes(window.location.port)
  const fallbackOrigin = isLocalFrontend
    ? `${window.location.protocol}//${window.location.hostname}:8000`
    : window.location.origin
  const url = new URL("/api/ws/notifications", apiBaseUrl || fallbackOrigin)

  url.protocol = url.protocol === "https:" ? "wss:" : "ws:"
  url.searchParams.set("token", token)
  return url.toString()
}

export const useNotificationStore = create<NotificationState>((set, get) => ({
  items: [],
  unreadCount: 0,
  loading: false,
  drawerVisible: false,
  ws: null,
  wsConnected: false,
  wsReconnectAttempts: 0,

  addNotification: (notification) => {
    const item: NotificationItem = {
      id: notification.id || `${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
      title: notification.title,
      content: notification.content,
      type: notification.type,
      status: notification.status ?? "unread",
      created_at: notification.created_at || new Date().toISOString(),
      link: notification.link,
      source: notification.source
    }

    set((state) => ({
      items: [item, ...state.items],
      unreadCount: item.status === "unread" ? state.unreadCount + 1 : state.unreadCount
    }))
  },

  setDrawerVisible: (visible) => set({ drawerVisible: visible }),

  refreshUnreadCount: async () => {
    const response = await notificationsApi.getUnreadCount()
    if (response.success) {
      set({ unreadCount: Number(response.data?.count || 0) })
    }
  },

  loadList: async (status = "all") => {
    set({ loading: true })
    try {
      const response = await notificationsApi.getList({ status, page: 1, page_size: 20 })
      if (response.success) {
        set({ items: response.data?.items || [] })
      }
    } finally {
      set({ loading: false })
    }
  },

  markRead: async (id) => {
    const response = await notificationsApi.markRead(id)
    if (response.success) {
      get().markReadLocal(id)
      await get().refreshUnreadCount()
    }
  },

  markAllRead: async () => {
    const response = await notificationsApi.markAllRead()
    if (response.success) {
      get().markAllReadLocal()
      await get().refreshUnreadCount()
    }
  },

  connectWebSocket: () => {
    if (typeof window === "undefined") return

    if (reconnectTimer) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }

    const activeSocket = get().ws
    if (activeSocket && [websocketConnectingState, websocketOpenState].includes(activeSocket.readyState)) {
      return
    }

    if (activeSocket) {
      manualDisconnect = true
      set({ ws: null, wsConnected: false })
      try {
        activeSocket.close()
      } catch {
        // noop
      }
    }

    manualDisconnect = false

    const token = useAuthStore.getState().token || localStorage.getItem("auth-token") || ""
    if (!token) return

    const socket = new WebSocket(getNotificationWebSocketUrl(token))

    socket.onopen = () => {
      if (get().ws !== socket) return
      set({
        wsConnected: true,
        wsReconnectAttempts: 0
      })
    }

    socket.onclose = () => {
      if (get().ws !== socket) return

      set({
        ws: null,
        wsConnected: false
      })

      if (manualDisconnect) return

      const attempts = get().wsReconnectAttempts
      if (attempts < maxReconnectAttempts) {
        reconnectTimer = setTimeout(() => {
          set({ wsReconnectAttempts: attempts + 1 })
          get().connectWebSocket()
        }, Math.min(1000 * Math.pow(2, attempts), 30000))
      }
    }

    socket.onerror = () => {
      if (get().ws !== socket) return
      set({ wsConnected: false })
    }

    socket.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data)
        if (message.type === "notification" && message.data?.title && message.data?.type) {
          get().addNotification(message.data)
        }
      } catch {
        // Ignore malformed notification frames; the connection remains usable.
      }
    }

    set({ ws: socket })
  },

  disconnectWebSocket: () => {
    manualDisconnect = true

    if (reconnectTimer) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }

    const socket = get().ws
    if (socket) {
      try {
        if (socket.readyState === websocketConnectingState) {
          socket.onopen = () => socket.close()
        } else {
          socket.close()
        }
      } catch {
        // noop
      }
    }

    set({
      ws: null,
      wsConnected: false,
      wsReconnectAttempts: 0
    })
  },

  connect: () => get().connectWebSocket(),

  disconnect: () => get().disconnectWebSocket(),

  markReadLocal: (id) =>
    set((state) => {
      const wasUnread = state.items.some((item) => item.id === id && item.status === "unread")
      return {
        items: state.items.map((item) => (item.id === id ? { ...item, status: "read" } : item)),
        unreadCount: wasUnread ? Math.max(0, state.unreadCount - 1) : state.unreadCount
      }
    }),

  markAllReadLocal: () =>
    set((state) => ({
      items: state.items.map((item) => ({ ...item, status: "read" })),
      unreadCount: 0
    }))
}))

export function resetNotificationStoreForTests() {
  if (reconnectTimer) {
    clearTimeout(reconnectTimer)
    reconnectTimer = null
  }
  manualDisconnect = false
  useNotificationStore.setState({
    items: [],
    unreadCount: 0,
    loading: false,
    drawerVisible: false,
    ws: null,
    wsConnected: false,
    wsReconnectAttempts: 0
  })
}
