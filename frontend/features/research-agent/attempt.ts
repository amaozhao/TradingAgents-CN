"use client"

import { useCallback, useRef } from "react"

type CompletionPollingOptions = {
  attemptId?: string
  intervalMs?: number
  onTimeout: () => void
  refresh: () => Promise<boolean>
  timeoutMs: number
}

export function useResearchAttempt() {
  const completionPollRef = useRef<number | null>(null)
  const runFinishedRef = useRef(false)
  const localRunningSessionRef = useRef<string | null>(null)

  const stopCompletionPolling = useCallback(() => {
    if (completionPollRef.current != null) {
      window.clearInterval(completionPollRef.current)
      completionPollRef.current = null
    }
  }, [])

  const markRunFinished = useCallback((finished: boolean) => {
    runFinishedRef.current = finished
  }, [])

  const isRunFinished = useCallback(() => runFinishedRef.current, [])

  const setLocalRunningSession = useCallback((sessionId: string | null) => {
    localRunningSessionRef.current = sessionId
  }, [])

  const getLocalRunningSession = useCallback(() => localRunningSessionRef.current, [])

  const startCompletionPolling = useCallback((options: CompletionPollingOptions) => {
    const { attemptId, intervalMs = 3_000, onTimeout, refresh, timeoutMs } = options
    stopCompletionPolling()
    if (!attemptId || runFinishedRef.current) return

    const startedAt = Date.now()
    void refresh().catch(() => undefined)
    completionPollRef.current = window.setInterval(() => {
      if (Date.now() - startedAt > timeoutMs) {
        stopCompletionPolling()
        runFinishedRef.current = true
        onTimeout()
        return
      }
      void refresh().catch(() => undefined)
    }, intervalMs)
  }, [stopCompletionPolling])

  return {
    getLocalRunningSession,
    isRunFinished,
    markRunFinished,
    setLocalRunningSession,
    startCompletionPolling,
    stopCompletionPolling
  }
}
