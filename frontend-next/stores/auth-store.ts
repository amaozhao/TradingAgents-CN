"use client"

import { create } from "zustand"

import {
  clearStoredAuth,
  loadStoredAuth,
  saveStoredAuth
} from "@/libs/auth/token-storage"
import type { User } from "@/types/auth"

export interface AuthState {
  hasHydrated: boolean
  isAuthenticated: boolean
  token: string | null
  refreshToken: string | null
  user: User | null
  permissions: string[]
  roles: string[]
  loginLoading: boolean
  redirectPath: string
  hydrateFromStorage: () => void
  setAuthInfo: (token: string, refreshToken?: string | null, user?: User | null) => void
  clearAuthInfo: () => void
  setPermissions: (permissions: string[]) => void
  setRoles: (roles: string[]) => void
  setLoginLoading: (loading: boolean) => void
  setRedirectPath: (path: string) => void
  getAndClearRedirectPath: () => string
  userAvatar: () => string | undefined
  userDisplayName: () => string
  isAdmin: () => boolean
  hasPermission: (permission: string) => boolean
  hasRole: (role: string) => boolean
  userStats: () => Record<string, number>
}

const initialState = {
  hasHydrated: false,
  isAuthenticated: false,
  token: null,
  refreshToken: null,
  user: null,
  permissions: [] as string[],
  roles: [] as string[],
  loginLoading: false,
  redirectPath: "/"
}

export const useAuthStore = create<AuthState>((set, get) => ({
  ...initialState,

  hydrateFromStorage: () => {
    const stored = loadStoredAuth()

    if (!stored) {
      set({
        ...initialState,
        hasHydrated: true
      })
      return
    }

    set({
      hasHydrated: true,
      isAuthenticated: true,
      token: stored.token,
      refreshToken: stored.refreshToken,
      user: stored.user
    })
  },

  setAuthInfo: (token, refreshToken, user) => {
    set({
      hasHydrated: true,
      token,
      refreshToken: refreshToken ?? get().refreshToken,
      user: user ?? get().user,
      isAuthenticated: true
    })

    saveStoredAuth({
      token,
      refreshToken,
      user
    })
  },

  clearAuthInfo: () => {
    clearStoredAuth()
    set({
      ...initialState,
      hasHydrated: true
    })
  },

  setPermissions: (permissions) => set({ permissions }),

  setRoles: (roles) => set({ roles }),

  setLoginLoading: (loading) => set({ loginLoading: loading }),

  setRedirectPath: (path) => set({ redirectPath: path }),

  getAndClearRedirectPath: () => {
    const path = get().redirectPath || "/dashboard"
    set({ redirectPath: "/" })
    return path === "/" ? "/dashboard" : path
  },

  userAvatar: () => get().user?.avatar || undefined,

  userDisplayName: () => get().user?.username || get().user?.email || "未知用户",

  isAdmin: () => get().roles.includes("admin"),

  hasPermission: (permission) => get().permissions.includes(permission) || get().isAdmin(),

  hasRole: (role) => get().roles.includes(role),

  userStats: () => ({
    totalAnalyses: Number(get().user?.total_analyses || 0),
    successfulAnalyses: Number(get().user?.successful_analyses || 0),
    failedAnalyses: Number(get().user?.failed_analyses || 0),
    dailyQuota: Number(get().user?.daily_quota || 1000),
    concurrentLimit: Number(get().user?.concurrent_limit || 3)
  })
}))

export function resetAuthStoreForTests() {
  clearStoredAuth()
  useAuthStore.setState({
    ...initialState
  })
}
