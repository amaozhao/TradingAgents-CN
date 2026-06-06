"use client"

import { useAuthStore } from "@/stores/auth-store"
import { downloadBlob } from "@/libs/utils/download"

export interface ReportListItem {
  id: string
  title: string
  stock_code?: string
  stock_name?: string
  type?: string
  format?: string
  status?: string
  model_info?: string
  created_at?: string
}

export interface ReportDetailData {
  id: string
  stock_symbol: string
  stock_name?: string
  status?: string
  recommendation?: string
  risk_level?: string
  confidence_score?: number
  summary?: string
  reports?: Record<string, string | Record<string, unknown>>
  created_at?: string
}

async function requestJson<T>(url: string): Promise<T> {
  const token = useAuthStore.getState().token
  const response = await fetch(url, {
    headers: token ? { Authorization: `Bearer ${token}` } : undefined
  })
  if (!response.ok) throw new Error(`HTTP ${response.status}`)
  const body = (await response.json()) as { data?: T }
  return body.data as T
}

export function fetchReports(params: URLSearchParams) {
  return requestJson<{ reports: ReportListItem[]; total: number }>(`/api/reports/list?${params.toString()}`)
}

export function fetchReportDetail(id: string) {
  return requestJson<ReportDetailData>(`/api/reports/${id}/detail`)
}

export async function downloadReport(id: string, format = "markdown", filename = "analysis-report.md") {
  const token = useAuthStore.getState().token
  const response = await fetch(`/api/reports/${id}/download?format=${encodeURIComponent(format)}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : undefined
  })
  if (!response.ok) {
    const message = await response.text()
    throw new Error(message || `HTTP ${response.status}`)
  }
  downloadBlob(await response.blob(), filename)
}
