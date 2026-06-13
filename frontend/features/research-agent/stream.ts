"use client"

import { useCallback, useRef } from "react"

import { researchAgentApi, type ParsedResearchStreamEvent } from "@/libs/api/research-agent"

type StreamHandlers = {
  onEvent: (item: ParsedResearchStreamEvent) => void
  onError?: () => void
}

export function useResearchStream() {
  const streamStopRef = useRef<(() => void) | null>(null)
  const lastEventIdRef = useRef("")
  const streamingAnswerIdRef = useRef<string | null>(null)

  const stopStream = useCallback(() => {
    streamStopRef.current?.()
    streamStopRef.current = null
    streamingAnswerIdRef.current = null
  }, [])

  const subscribeToSession = useCallback((sessionId: string, handlers: StreamHandlers) => {
    stopStream()
    streamStopRef.current = researchAgentApi.subscribeEvents(sessionId, handlers, lastEventIdRef.current)
  }, [stopStream])

  const setLastEventId = useCallback((eventId: string) => {
    lastEventIdRef.current = eventId
  }, [])

  const resetLastEventId = useCallback(() => {
    lastEventIdRef.current = ""
  }, [])

  const getStreamingAnswerId = useCallback(() => streamingAnswerIdRef.current, [])

  const setStreamingAnswerId = useCallback((messageId: string) => {
    streamingAnswerIdRef.current = messageId
  }, [])

  const clearStreamingAnswerId = useCallback(() => {
    streamingAnswerIdRef.current = null
  }, [])

  return {
    clearStreamingAnswerId,
    getStreamingAnswerId,
    resetLastEventId,
    setLastEventId,
    setStreamingAnswerId,
    stopStream,
    subscribeToSession
  }
}
