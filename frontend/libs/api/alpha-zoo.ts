import { ApiClient } from "@/libs/api/request"

export interface AlphaFactor {
  factor_id: string
  family: string
  number: number
  name: string
  description: string
  required_columns: string[]
}

export interface AlphaFactorList {
  items: AlphaFactor[]
  total: number
}

export interface AlphaJob {
  job_id: string
  status: string
  result?: Record<string, unknown>
}

export const alphaZooApi = {
  list: (params?: { family?: string; search?: string }) =>
    ApiClient.get<AlphaFactorList>("/api/alpha-zoo/list", params),
  detail: (alphaId: string) => ApiClient.get<AlphaFactor>(`/api/alpha-zoo/${alphaId}`),
  bench: (payload: { alpha_id: string; symbols: string[]; start_date?: string; end_date?: string }) =>
    ApiClient.post<AlphaJob>("/api/alpha-zoo/bench", payload),
  compare: (payload: { alpha_ids: string[]; symbols: string[]; start_date?: string; end_date?: string }) =>
    ApiClient.post<AlphaJob>("/api/alpha-zoo/compare", payload),
  getJob: (jobId: string) => ApiClient.get<AlphaJob>(`/api/alpha-zoo/jobs/${jobId}`),
  listEvents: (jobId: string, afterEventId = 0) =>
    ApiClient.get<Record<string, unknown>[]>(`/api/alpha-zoo/jobs/${jobId}/events`, { after_event_id: afterEventId })
}
