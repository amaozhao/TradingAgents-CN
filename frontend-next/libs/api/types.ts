import type { AxiosRequestConfig } from "axios"

export interface ApiResponse<T = unknown> {
  success: boolean
  data: T
  message: string
  code?: number
  timestamp?: string
  request_id?: string
}

export interface RequestConfig<D = unknown> extends AxiosRequestConfig<D> {
  skipAuth?: boolean
  skipAuthError?: boolean
  skipErrorHandler?: boolean
  showLoading?: boolean
  loadingText?: string
  retryCount?: number
  retryDelay?: number
}

/* eslint-disable @typescript-eslint/no-explicit-any, @typescript-eslint/no-unused-vars */
declare module "axios" {
  export interface AxiosRequestConfig<D = any> {
    skipAuth?: boolean
    skipAuthError?: boolean
    skipErrorHandler?: boolean
    showLoading?: boolean
    loadingText?: string
    retryCount?: number
    retryDelay?: number
  }

  export interface InternalAxiosRequestConfig<D = any> {
    skipAuth?: boolean
    skipAuthError?: boolean
    skipErrorHandler?: boolean
    showLoading?: boolean
    loadingText?: string
    retryCount?: number
    retryDelay?: number
  }
}
/* eslint-enable @typescript-eslint/no-explicit-any, @typescript-eslint/no-unused-vars */
