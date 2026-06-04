import type { User } from "@/types/auth"

export const AUTH_TOKEN_KEY = "auth-token"
export const REFRESH_TOKEN_KEY = "refresh-token"
export const USER_INFO_KEY = "user-info"

export interface StoredAuthInfo {
  token: string
  refreshToken: string
  user: User | null
}

type StorageLike = Pick<Storage, "getItem" | "setItem" | "removeItem">

function getBrowserStorage(storage?: StorageLike): StorageLike | null {
  if (storage) return storage
  if (typeof window === "undefined") return null
  return window.localStorage
}

export function isValidJwtLikeToken(token: string | null | undefined): token is string {
  if (!token || typeof token !== "string") return false
  if (token === "mock-token" || token.startsWith("mock-")) return false
  return token.split(".").length === 3
}

export function clearStoredAuth(storage?: StorageLike) {
  const target = getBrowserStorage(storage)
  if (!target) return

  target.removeItem(AUTH_TOKEN_KEY)
  target.removeItem(REFRESH_TOKEN_KEY)
  target.removeItem(USER_INFO_KEY)
}

export function saveStoredAuth(
  auth: {
    token: string
    refreshToken?: string | null
    user?: User | null
  },
  storage?: StorageLike
) {
  const target = getBrowserStorage(storage)
  if (!target) return

  target.setItem(AUTH_TOKEN_KEY, auth.token)

  if (auth.refreshToken) {
    target.setItem(REFRESH_TOKEN_KEY, auth.refreshToken)
  }

  if (auth.user) {
    target.setItem(USER_INFO_KEY, JSON.stringify(auth.user))
  }
}

export function loadStoredAuth(storage?: StorageLike): StoredAuthInfo | null {
  const target = getBrowserStorage(storage)
  if (!target) return null

  const token = target.getItem(AUTH_TOKEN_KEY)
  const refreshToken = target.getItem(REFRESH_TOKEN_KEY)

  if (!isValidJwtLikeToken(token) || !isValidJwtLikeToken(refreshToken)) {
    clearStoredAuth(target)
    return null
  }

  const rawUser = target.getItem(USER_INFO_KEY)
  let user: User | null = null

  if (rawUser) {
    try {
      user = JSON.parse(rawUser) as User
    } catch {
      user = null
    }
  }

  return {
    token,
    refreshToken,
    user
  }
}
