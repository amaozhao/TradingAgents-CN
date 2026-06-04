import { describe, expect, it } from "vitest"

import {
  AUTH_TOKEN_KEY,
  REFRESH_TOKEN_KEY,
  USER_INFO_KEY,
  clearStoredAuth,
  isValidJwtLikeToken,
  loadStoredAuth,
  saveStoredAuth
} from "@/libs/auth/token-storage"

describe("token storage", () => {
  it("accepts JWT-like tokens and rejects mock or malformed tokens", () => {
    expect(isValidJwtLikeToken("header.payload.signature")).toBe(true)
    expect(isValidJwtLikeToken("mock-token")).toBe(false)
    expect(isValidJwtLikeToken("mock-anything")).toBe(false)
    expect(isValidJwtLikeToken("not-a-jwt")).toBe(false)
    expect(isValidJwtLikeToken(null)).toBe(false)
  })

  it("persists and loads current auth keys", () => {
    saveStoredAuth({
      token: "access.payload.sig",
      refreshToken: "refresh.payload.sig",
      user: { username: "trader", email: "trader@example.com" }
    })

    expect(localStorage.getItem(AUTH_TOKEN_KEY)).toBe("access.payload.sig")
    expect(localStorage.getItem(REFRESH_TOKEN_KEY)).toBe("refresh.payload.sig")
    expect(JSON.parse(localStorage.getItem(USER_INFO_KEY) || "{}")).toEqual({
      username: "trader",
      email: "trader@example.com"
    })
    expect(loadStoredAuth()).toEqual({
      token: "access.payload.sig",
      refreshToken: "refresh.payload.sig",
      user: { username: "trader", email: "trader@example.com" }
    })
  })

  it("clears all auth keys when stored tokens are invalid", () => {
    localStorage.setItem(AUTH_TOKEN_KEY, "mock-token")
    localStorage.setItem(REFRESH_TOKEN_KEY, "refresh.payload.sig")
    localStorage.setItem(USER_INFO_KEY, JSON.stringify({ username: "stale" }))

    expect(loadStoredAuth()).toBeNull()
    expect(localStorage.getItem(AUTH_TOKEN_KEY)).toBeNull()
    expect(localStorage.getItem(REFRESH_TOKEN_KEY)).toBeNull()
    expect(localStorage.getItem(USER_INFO_KEY)).toBeNull()
  })

  it("clears stored auth keys explicitly", () => {
    saveStoredAuth({
      token: "access.payload.sig",
      refreshToken: "refresh.payload.sig",
      user: { username: "trader" }
    })

    clearStoredAuth()

    expect(localStorage.getItem(AUTH_TOKEN_KEY)).toBeNull()
    expect(localStorage.getItem(REFRESH_TOKEN_KEY)).toBeNull()
    expect(localStorage.getItem(USER_INFO_KEY)).toBeNull()
  })
})
