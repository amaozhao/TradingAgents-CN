"use client"

import { useCallback, useEffect, useRef, useState } from "react"

import { researchAgentApi, type ResearchSession } from "@/libs/api/research-agent"

type EnsureSessionResult = {
  sessionId: string
  created: boolean
}

export function useResearchSession() {
  const [sessions, setSessions] = useState<ResearchSession[]>([])
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null)
  const loadSeqRef = useRef(0)

  const refreshSessions = useCallback(async () => {
    try {
      const response = await researchAgentApi.listSessions()
      setSessions(response.data || [])
    } catch {
      setSessions([])
    }
  }, [])

  useEffect(() => {
    void researchAgentApi.listSessions().then((response) => {
      setSessions(response.data || [])
    }).catch(() => setSessions([]))
  }, [])

  const ensureSession = useCallback(async (title: string): Promise<EnsureSessionResult> => {
    if (activeSessionId) return { sessionId: activeSessionId, created: false }
    const response = await researchAgentApi.createSession({ title: title.slice(0, 50) || "Agent session" })
    const session = response.data
    setActiveSessionId(session.session_id)
    setSessions((current) => [session, ...current])
    return { sessionId: session.session_id, created: true }
  }, [activeSessionId])

  const renameSession = useCallback(async (sessionId: string, title: string) => {
    const response = await researchAgentApi.updateSession(sessionId, { title })
    setSessions((current) => current.map((session) => (
      session.session_id === sessionId ? response.data : session
    )))
  }, [])

  const deleteSession = useCallback(async (sessionId: string) => {
    await researchAgentApi.deleteSession(sessionId)
    setSessions((current) => current.filter((session) => session.session_id !== sessionId))
  }, [])

  const nextLoadSeq = useCallback(() => {
    const nextSeq = loadSeqRef.current + 1
    loadSeqRef.current = nextSeq
    return nextSeq
  }, [])

  const isCurrentLoadSeq = useCallback((loadSeq: number) => loadSeqRef.current === loadSeq, [])

  const invalidateLoad = useCallback(() => {
    loadSeqRef.current += 1
  }, [])

  return {
    activeSessionId,
    deleteSession,
    ensureSession,
    invalidateLoad,
    isCurrentLoadSeq,
    nextLoadSeq,
    refreshSessions,
    renameSession,
    sessions,
    setActiveSessionId
  }
}
