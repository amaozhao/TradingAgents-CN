import type { AxiosRequestConfig } from "axios"

import { apiClient } from "@/libs/api/client"
import type { ApiResponse, RequestConfig } from "@/libs/api/types"

type RequestInstance = {
  <T = unknown>(config: RequestConfig): Promise<T>
  get<T = unknown>(url: string, config?: RequestConfig): Promise<T>
  post<T = unknown>(url: string, data?: unknown, config?: RequestConfig): Promise<T>
  put<T = unknown>(url: string, data?: unknown, config?: RequestConfig): Promise<T>
  delete<T = unknown>(url: string, config?: RequestConfig): Promise<T>
  patch<T = unknown>(url: string, data?: unknown, config?: RequestConfig): Promise<T>
  request<T = unknown>(config: RequestConfig): Promise<T>
}

export const request = apiClient as unknown as RequestInstance

export async function testApiConnection(): Promise<boolean> {
  try {
    await request.get("/api/health", {
      timeout: 5_000,
      skipErrorHandler: true
    })
    return true
  } catch {
    return false
  }
}

export class ApiClient {
  static get<T = unknown>(url: string, params?: unknown, config?: RequestConfig): Promise<ApiResponse<T>> {
    return request.get<ApiResponse<T>>(url, { params, ...config })
  }

  static post<T = unknown>(url: string, data?: unknown, config?: RequestConfig): Promise<ApiResponse<T>> {
    return request.post<ApiResponse<T>>(url, data, config)
  }

  static put<T = unknown>(url: string, data?: unknown, config?: RequestConfig): Promise<ApiResponse<T>> {
    return request.put<ApiResponse<T>>(url, data, config)
  }

  static delete<T = unknown>(url: string, config?: RequestConfig): Promise<ApiResponse<T>> {
    return request.delete<ApiResponse<T>>(url, config)
  }

  static patch<T = unknown>(url: string, data?: unknown, config?: RequestConfig): Promise<ApiResponse<T>> {
    return request.patch<ApiResponse<T>>(url, data, config)
  }

  static upload<T = unknown>(
    url: string,
    file: File,
    onProgress?: (progress: number) => void,
    config?: RequestConfig
  ): Promise<ApiResponse<T>> {
    const formData = new FormData()
    formData.append("file", file)

    return request.post<ApiResponse<T>>(url, formData, {
      headers: {
        "Content-Type": "multipart/form-data"
      },
      onUploadProgress: (progressEvent) => {
        if (onProgress && progressEvent.total) {
          onProgress(Math.round((progressEvent.loaded * 100) / progressEvent.total))
        }
      },
      ...config
    })
  }

  static async download(url: string, filename = "download", config?: RequestConfig): Promise<void> {
    const blobData = await apiClient.get<BlobPart, BlobPart>(url, {
      responseType: "blob",
      ...config
    } as AxiosRequestConfig)
    const blob = blobData instanceof Blob ? blobData : new Blob([blobData])
    const downloadUrl = window.URL.createObjectURL(blob)
    const link = document.createElement("a")
    link.href = downloadUrl
    link.download = filename
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(downloadUrl)
  }
}

export type { ApiResponse, RequestConfig }
export default request
