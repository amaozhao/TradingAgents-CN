import { describe, expect, it } from "vitest"

import { AUTH_TOKEN_KEY, REFRESH_TOKEN_KEY, USER_INFO_KEY } from "@/libs/auth/token-storage"
import { resetAuthStoreForTests, useAuthStore } from "@/stores/auth-store"

describe("auth store", () => {
  beforeEach(() => {
    resetAuthStoreForTests()
  })

  it("sets auth state and mirrors current localStorage keys", () => {
    useAuthStore.getState().setAuthInfo("access.payload.sig", "refresh.payload.sig", {
      username: "admin",
      email: "admin@example.com"
    })

    const state = useAuthStore.getState()
    expect(state.isAuthenticated).toBe(true)
    expect(state.token).toBe("access.payload.sig")
    expect(state.refreshToken).toBe("refresh.payload.sig")
    expect(state.userDisplayName()).toBe("admin")
    expect(localStorage.getItem(AUTH_TOKEN_KEY)).toBe("access.payload.sig")
    expect(localStorage.getItem(REFRESH_TOKEN_KEY)).toBe("refresh.payload.sig")
    expect(JSON.parse(localStorage.getItem(USER_INFO_KEY) || "{}")).toEqual({
      username: "admin",
      email: "admin@example.com"
    })
  })

  it("clears auth state, permissions, roles, and storage", () => {
    useAuthStore.getState().setAuthInfo("access.payload.sig", "refresh.payload.sig", {
      username: "admin"
    })
    useAuthStore.getState().setPermissions(["*"])
    useAuthStore.getState().setRoles(["admin"])

    useAuthStore.getState().clearAuthInfo()

    const state = useAuthStore.getState()
    expect(state.isAuthenticated).toBe(false)
    expect(state.token).toBeNull()
    expect(state.refreshToken).toBeNull()
    expect(state.user).toBeNull()
    expect(state.permissions).toEqual([])
    expect(state.roles).toEqual([])
    expect(localStorage.getItem(AUTH_TOKEN_KEY)).toBeNull()
  })

  it("hydrates valid storage and discards invalid storage", () => {
    localStorage.setItem(AUTH_TOKEN_KEY, "access.payload.sig")
    localStorage.setItem(REFRESH_TOKEN_KEY, "refresh.payload.sig")
    localStorage.setItem(USER_INFO_KEY, JSON.stringify({ email: "stored@example.com" }))

    useAuthStore.getState().hydrateFromStorage()
    expect(useAuthStore.getState().isAuthenticated).toBe(true)
    expect(useAuthStore.getState().userDisplayName()).toBe("stored@example.com")

    localStorage.setItem(AUTH_TOKEN_KEY, "mock-token")
    useAuthStore.getState().hydrateFromStorage()
    expect(useAuthStore.getState().isAuthenticated).toBe(false)
    expect(localStorage.getItem(AUTH_TOKEN_KEY)).toBeNull()
  })
})
