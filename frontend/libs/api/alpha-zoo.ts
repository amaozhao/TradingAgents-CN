import { ApiClient } from "@/libs/api/request"

export interface AlphaFactor {
  factor_id: string
  id: string
  family: string
  zoo: string
  number: number
  name: string
  nickname: string
  description: string
  required_columns: string[]
  columns_required: string[]
  theme: string[]
  formula_latex: string
  extras_required: string[]
  requires_sector: boolean
  universe: string[]
  frequency: string[]
  decay_horizon?: number | null
  min_warmup_bars?: number | null
  notes: string
  module_path: string
  meta: Record<string, unknown>
}

export interface AlphaFactorList {
  items: AlphaFactor[]
  alphas: AlphaFactor[]
  total: number
  returned: number
  truncated: boolean
  health?: {
    loaded: number
    failed: number
    errors: { alpha_id: string; reason: string }[]
  }
}

export interface AlphaFactorDetail extends AlphaFactor {
  alpha: {
    id: string
    zoo: string
    module_path: string
    meta: Record<string, unknown>
  }
  source_code: string
}

export interface AlphaJob {
  job_id: string
  status: string
  result?: Record<string, unknown>
}

export const alphaZooApi = {
  list: (params?: { family?: string; zoo?: string; theme?: string; universe?: string; search?: string; limit?: number }) =>
    ApiClient.get<AlphaFactorList>("/api/alpha-zoo/list", params),
  detail: (alphaId: string) => ApiClient.get<AlphaFactorDetail>(`/api/alpha-zoo/${encodeURIComponent(alphaId)}`),
  bench: (payload: { alpha_id: string; symbols: string[]; start_date?: string; end_date?: string }) =>
    ApiClient.post<AlphaJob>("/api/alpha-zoo/bench", payload),
  compare: (payload: { alpha_ids: string[]; symbols: string[]; start_date?: string; end_date?: string }) =>
    ApiClient.post<AlphaJob>("/api/alpha-zoo/compare", payload),
  getJob: (jobId: string) => ApiClient.get<AlphaJob>(`/api/alpha-zoo/jobs/${jobId}`),
  listEvents: (jobId: string, afterEventId = 0) =>
    ApiClient.get<Record<string, unknown>[]>(`/api/alpha-zoo/jobs/${jobId}/events`, { after_event_id: afterEventId })
}
