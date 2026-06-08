import { ApiClient } from "@/libs/api/request"

export interface CorrelationJob {
  job_id: string
  status: string
  result?: {
    artifact_id?: string
    matrix?: Record<string, Record<string, number>>
    high_correlation_pairs?: Array<Record<string, unknown>>
    diversification_candidates?: Array<Record<string, unknown>>
  }
}

export const researchMatrixApi = {
  correlation: (payload: {
    symbols?: string[]
    method?: string
    window?: number
    screening_result_id?: string
    sector?: string
    favorites_id?: string
    universe_id?: string
  }) => ApiClient.post<CorrelationJob>("/api/research-matrix/correlation", payload),
  getJob: (jobId: string) => ApiClient.get<CorrelationJob>(`/api/research-matrix/jobs/${jobId}`),
  listEvents: (jobId: string, afterEventId = 0) =>
    ApiClient.get<Record<string, unknown>[]>(`/api/research-matrix/jobs/${jobId}/events`, { after_event_id: afterEventId })
}
