"use client"

import { useEffect } from "react"

import { testApiConnection } from "@/libs/api/request"
import { useAppStore } from "@/stores/app-store"
import { useAuthStore } from "@/stores/auth-store"

export function AppInitializer() {
  const hydrateFromStorage = useAuthStore((state) => state.hydrateFromStorage)
  const setOnlineStatus = useAppStore((state) => state.setOnlineStatus)
  const checkApiConnection = useAppStore((state) => state.checkApiConnection)

  useEffect(() => {
    hydrateFromStorage()
    setOnlineStatus(navigator.onLine)
    checkApiConnection(testApiConnection).catch(() => {
      useAppStore.getState().setApiConnected(false)
    })

    const handleOnline = () => {
      setOnlineStatus(true)
      checkApiConnection(testApiConnection).catch(() => {
        useAppStore.getState().setApiConnected(false)
      })
    }
    const handleOffline = () => {
      setOnlineStatus(false)
      useAppStore.getState().setApiConnected(false)
    }

    window.addEventListener("online", handleOnline)
    window.addEventListener("offline", handleOffline)

    return () => {
      window.removeEventListener("online", handleOnline)
      window.removeEventListener("offline", handleOffline)
    }
  }, [checkApiConnection, hydrateFromStorage, setOnlineStatus])

  return null
}
