"use client"

import { create } from "zustand"

export type AppTheme = "light" | "dark" | "auto"
export type AppLanguage = "zh-CN" | "en-US"

export interface AppPreferences {
  defaultMarket: "A股" | "美股" | "港股"
  defaultDepth: "1" | "2" | "3" | "4" | "5"
  autoRefresh: boolean
  refreshInterval: number
  showWelcome: boolean
}

export interface AppState {
  loading: boolean
  loadingProgress: number
  theme: AppTheme
  language: AppLanguage
  isOnline: boolean
  apiConnected: boolean
  lastApiCheck: number
  sidebarCollapsed: boolean
  sidebarWidth: number
  preferences: AppPreferences
  version: string
  buildTime: string
  apiVersion: string
  setLoading: (loading: boolean, progress?: number) => void
  setLanguage: (language: AppLanguage) => void
  setTheme: (theme: AppTheme) => void
  setOnlineStatus: (isOnline: boolean) => void
  setApiConnected: (connected: boolean) => void
  setSidebarCollapsed: (collapsed: boolean) => void
  setSidebarWidth: (width: number) => void
  updatePreferences: (preferences: Partial<AppPreferences>) => void
  resetPreferences: () => void
}

const defaultPreferences: AppPreferences = {
  defaultMarket: "A股",
  defaultDepth: "3",
  autoRefresh: true,
  refreshInterval: 30,
  showWelcome: true
}

function readStorageValue<T>(key: string, fallback: T): T {
  if (typeof window === "undefined") return fallback
  const value = window.localStorage.getItem(key)
  if (!value) return fallback

  try {
    return JSON.parse(value) as T
  } catch {
    return value as T
  }
}

function writeStorageValue(key: string, value: unknown) {
  if (typeof window === "undefined") return
  window.localStorage.setItem(key, typeof value === "string" ? value : JSON.stringify(value))
}

export const useAppStore = create<AppState>((set) => ({
  loading: false,
  loadingProgress: 0,
  theme: readStorageValue<AppTheme>("app-theme", "auto"),
  language: readStorageValue<AppLanguage>("app-language", "zh-CN"),
  isOnline: typeof navigator === "undefined" ? true : navigator.onLine,
  apiConnected: false,
  lastApiCheck: 0,
  sidebarCollapsed: readStorageValue<boolean>("sidebar-collapsed", false),
  sidebarWidth: readStorageValue<number>("sidebar-width", 240),
  preferences: readStorageValue<AppPreferences>("user-preferences", defaultPreferences),
  version: "1.0.1",
  buildTime: new Date().toISOString(),
  apiVersion: "",

  setLoading: (loading, progress = 0) =>
    set({
      loading,
      loadingProgress: Math.max(0, Math.min(100, progress))
    }),

  setLanguage: (language) => {
    writeStorageValue("app-language", language)
    if (typeof document !== "undefined") {
      document.documentElement.lang = language
    }
    set({ language })
  },

  setTheme: (theme) => {
    writeStorageValue("app-theme", theme)
    set({ theme })
  },

  setOnlineStatus: (isOnline) => set({ isOnline }),

  setApiConnected: (connected) =>
    set({
      apiConnected: connected,
      lastApiCheck: Date.now()
    }),

  setSidebarCollapsed: (collapsed) => {
    writeStorageValue("sidebar-collapsed", collapsed)
    set({ sidebarCollapsed: collapsed })
  },

  setSidebarWidth: (width) => {
    const sidebarWidth = Math.max(200, Math.min(400, width))
    writeStorageValue("sidebar-width", sidebarWidth)
    set({ sidebarWidth })
  },

  updatePreferences: (preferences) =>
    set((state) => {
      const next = {
        ...state.preferences,
        ...preferences
      }
      writeStorageValue("user-preferences", next)
      return { preferences: next }
    }),

  resetPreferences: () => {
    writeStorageValue("user-preferences", defaultPreferences)
    set({ preferences: defaultPreferences })
  }
}))
