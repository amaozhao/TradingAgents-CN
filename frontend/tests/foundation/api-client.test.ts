import type { AxiosAdapter, AxiosResponse } from "axios"
import { describe, expect, it, vi } from "vitest"

import { createApiClient, isAuthErrorCode } from "@/libs/api/client"
import type { RequestConfig } from "@/libs/api/types"

interface CapturedConfig {
  headers: Record<string, string>
  url?: string
  params?: Record<string, unknown>
}

function toCapturedConfig(config: RequestConfig): CapturedConfig {
  return {
    headers: config.headers as Record<string, string>,
    url: config.url,
    params: config.params as Record<string, unknown> | undefined
  }
}

function adapterWithResponse<T>(data: T, status = 200, capture?: (config: CapturedConfig) => void): AxiosAdapter {
  return async (config) => {
    capture?.(toCapturedConfig(config))
    return {
      data,
      status,
      statusText: "OK",
      headers: {},
      config,
      request: {}
    } satisfies AxiosResponse<T>
  }
}

describe("api client", () => {
  it("classifies existing business auth error codes", () => {
    expect(isAuthErrorCode(401)).toBe(true)
    expect(isAuthErrorCode(40101)).toBe(true)
    expect(isAuthErrorCode(40102)).toBe(true)
    expect(isAuthErrorCode(40103)).toBe(true)
    expect(isAuthErrorCode(403)).toBe(false)
  })

  it("adds auth, language, request ID, and default headers", async () => {
    let captured: CapturedConfig | undefined
    const client = createApiClient({
      adapter: adapterWithResponse({ success: true, data: { ok: true }, message: "ok" }, 200, (config) => {
        captured = config
      }),
      getLanguage: () => "zh-CN",
      getToken: () => "access.payload.sig"
    })

    await client.get("/api/example")

    expect(captured?.headers.Authorization).toBe("Bearer access.payload.sig")
    expect(captured?.headers["Accept-Language"]).toBe("zh-CN")
    expect(captured?.headers["X-Request-ID"]).toMatch(/^req_/)
    expect(captured?.headers["Cache-Control"]).toBe("no-cache")
  })

  it("returns successful ApiResponse payloads directly", async () => {
    const client = createApiClient({
      adapter: adapterWithResponse({
        success: true,
        data: { value: 42 },
        message: "ok"
      })
    })

    await expect(client.get("/api/example")).resolves.toEqual({
      success: true,
      data: { value: 42 },
      message: "ok"
    })
  })

  it("rejects non-auth business errors without auth cleanup", async () => {
    const onAuthError = vi.fn()
    const client = createApiClient({
      adapter: adapterWithResponse({
        success: false,
        data: null,
        message: "参数错误",
        code: 40001
      }),
      onAuthError
    })

    await expect(client.get("/api/example")).rejects.toThrow("参数错误")
    expect(onAuthError).not.toHaveBeenCalled()
  })

  it("handles business auth errors before generic error handling", async () => {
    const onAuthError = vi.fn()
    const client = createApiClient({
      adapter: adapterWithResponse({
        success: false,
        data: null,
        message: "登录已过期",
        code: 40101
      }),
      getToken: () => "access.payload.sig",
      onAuthError
    })

    await expect(client.get("/api/protected")).rejects.toThrow("登录已过期")
    expect(onAuthError).toHaveBeenCalledWith("登录已过期")
  })

  it("respects skipAuthError while still rejecting the failed response", async () => {
    const onAuthError = vi.fn()
    const client = createApiClient({
      adapter: adapterWithResponse({
        success: false,
        data: null,
        message: "认证失败",
        code: 401
      }),
      onAuthError
    })

    await expect(client.get("/api/auth/login", { skipAuthError: true })).rejects.toThrow("认证失败")
    expect(onAuthError).not.toHaveBeenCalled()
  })

  it("rewrites legacy stock quote requests when code is supplied", async () => {
    let captured: CapturedConfig | undefined
    const client = createApiClient({
      adapter: adapterWithResponse({ success: true, data: {}, message: "ok" }, 200, (config) => {
        captured = config
      })
    })

    await client.get("/api/stocks/quote", { params: { code: "AAPL" } })

    expect(captured?.url).toBe("/api/stocks/AAPL/quote")
    expect(captured?.params).toEqual({})
  })

  it("rejects legacy stock quote requests without code", async () => {
    const client = createApiClient({
      adapter: adapterWithResponse({ success: true, data: {}, message: "ok" })
    })

    await expect(client.get("/api/stocks/quote")).rejects.toThrow("缺少 code")
  })
})
