import axios, { type AxiosAdapter, type AxiosInstance } from "axios"

import { loadStoredAuth } from "@/libs/auth/token-storage"
import { queryClient } from "@/libs/api/query-client"
import type { ApiResponse, RequestConfig } from "@/libs/api/types"
import { useAppStore } from "@/stores/app-store"
import { useAuthStore } from "@/stores/auth-store"

export interface ApiClientOptions {
  adapter?: AxiosAdapter
  baseURL?: string
  getToken?: () => string | null
  getLanguage?: () => string
  onAuthError?: (message: string) => void
  onLoadingChange?: (loading: boolean) => void
}

const AUTH_ERROR_CODES = new Set([401, 40101, 40102, 40103])

export function isAuthErrorCode(code: unknown) {
  return typeof code === "number" && AUTH_ERROR_CODES.has(code)
}

export function generateRequestId() {
  return `req_${Date.now()}_${Math.random().toString(36).slice(2, 10)}`
}

function normalizeBaseURL(baseURL?: string) {
  return baseURL ?? process.env.NEXT_PUBLIC_API_BASE_URL ?? ""
}

function handleLegacyStockQuoteEndpoint(config: RequestConfig) {
  const rawUrl = String(config.url || "")
  const pathOnly = rawUrl.split("?")[0].replace(/\/+$|^\s+|\s+$/g, "")

  if (pathOnly !== "/api/stocks/quote") return

  const params = (config.params || {}) as Record<string, unknown>
  const code = params.code ?? params.stock_code

  if (!code) {
    throw new Error("前端误用端点：缺少 code，请改用 /api/stocks/{code}/quote")
  }

  config.url = `/api/stocks/${String(code)}/quote`
  delete params.code
  delete params.stock_code
  config.params = params
}

function defaultAuthErrorHandler(message: string) {
  useAuthStore.getState().clearAuthInfo()
  queryClient.clear()

  if (typeof window !== "undefined" && window.location.pathname !== "/login") {
    window.location.assign("/login")
  }

  return message
}

export function createApiClient(options: ApiClientOptions = {}): AxiosInstance {
  const instance = axios.create({
    adapter: options.adapter,
    baseURL: normalizeBaseURL(options.baseURL),
    timeout: 60_000,
    headers: {
      "Content-Type": "application/json",
      "Cache-Control": "no-cache",
      Pragma: "no-cache"
    }
  })

  instance.interceptors.request.use((config) => {
    const requestConfig = config as RequestConfig
    const headers = requestConfig.headers as Record<string, string>

    handleLegacyStockQuoteEndpoint(requestConfig)

    if (!requestConfig.skipAuth) {
      const token =
        options.getToken?.() ||
        useAuthStore.getState().token ||
        loadStoredAuth()?.token ||
        null

      if (token) {
        headers.Authorization = `Bearer ${token}`
      }
    }

    headers["X-Request-ID"] = generateRequestId()
    headers["Accept-Language"] = options.getLanguage?.() || useAppStore.getState().language

    if (requestConfig.showLoading) {
      options.onLoadingChange?.(true)
      useAppStore.getState().setLoading(true, 0)
    }

    return requestConfig as typeof config
  })

  instance.interceptors.response.use(
    (response) => {
      const config = response.config as RequestConfig

      if (config.showLoading) {
        options.onLoadingChange?.(false)
        useAppStore.getState().setLoading(false)
      }

      const data = response.data as ApiResponse

      if (data && typeof data === "object" && "success" in data && !data.success) {
        const message = data.message || "请求失败"

        if (isAuthErrorCode(data.code)) {
          if (!config.skipAuthError) {
            ;(options.onAuthError || defaultAuthErrorHandler)(message || "登录已过期，请重新登录")
          }

          return Promise.reject(new Error(message || "认证失败"))
        }

        if (!config.skipErrorHandler) {
          return Promise.reject(new Error(message))
        }
      }

      return response.data
    },
    (error) => {
      const config = error.config as RequestConfig | undefined

      if (config?.showLoading) {
        options.onLoadingChange?.(false)
        useAppStore.getState().setLoading(false)
      }

      const message =
        error.response?.data?.detail ||
        error.response?.data?.message ||
        error.message ||
        "网络请求失败"

      if (error.response?.status === 401 && !config?.skipAuthError) {
        ;(options.onAuthError || defaultAuthErrorHandler)(message || "登录已过期，请重新登录")
      }

      return Promise.reject(error instanceof Error ? error : new Error(message))
    }
  )

  return instance
}

export const apiClient = createApiClient()
