"use client"

import { create } from "zustand"

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
  connectWebSocket: () => void
  disconnectWebSocket: () => void
  markReadLocal: (id: string) => void
  markAllReadLocal: () => void
}

let reconnectTimer: ReturnType<typeof setTimeout> | null = null
const maxReconnectAttempts = 10

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

  connectWebSocket: () => {
    if (typeof window === "undefined") return

    get().disconnectWebSocket()

    const token = useAuthStore.getState().token || localStorage.getItem("auth-token") || ""
    if (!token) return

    const wsProtocol = window.location.protocol === "https:" ? "wss:" : "ws:"
    const socket = new WebSocket(
      `${wsProtocol}//${window.location.host}/api/ws/notifications?token=${encodeURIComponent(token)}`
    )

    socket.onopen = () => {
      set({
        wsConnected: true,
        wsReconnectAttempts: 0
      })
    }

    socket.onclose = () => {
      set({
        ws: null,
        wsConnected: false
      })

      const attempts = get().wsReconnectAttempts
      if (attempts < maxReconnectAttempts) {
        reconnectTimer = setTimeout(() => {
          set({ wsReconnectAttempts: attempts + 1 })
          get().connectWebSocket()
        }, Math.min(1000 * Math.pow(2, attempts), 30000))
      }
    }

    socket.onerror = () => {
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
    if (reconnectTimer) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }

    const socket = get().ws
    if (socket) {
      try {
        socket.close()
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

  markReadLocal: (id) =>
    set((state) => ({
      items: state.items.map((item) => (item.id === id ? { ...item, status: "read" } : item)),
      unreadCount: Math.max(0, state.unreadCount - 1)
    })),

  markAllReadLocal: () =>
    set((state) => ({
      items: state.items.map((item) => ({ ...item, status: "read" })),
      unreadCount: 0
    }))
}))
