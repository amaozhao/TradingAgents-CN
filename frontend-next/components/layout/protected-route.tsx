"use client"

import { Suspense, useEffect } from "react"
import { usePathname, useRouter, useSearchParams } from "next/navigation"

import { useAuthStore } from "@/stores/auth-store"

interface GuardProps {
  children: React.ReactNode
}

export function ProtectedRoute({ children }: GuardProps) {
  return (
    <Suspense fallback={<RouteFallback />}>
      <ProtectedRouteInner>{children}</ProtectedRouteInner>
    </Suspense>
  )
}

function ProtectedRouteInner({ children }: GuardProps) {
  const router = useRouter()
  const pathname = usePathname()
  const searchParams = useSearchParams()
  const hasHydrated = useAuthStore((state) => state.hasHydrated)
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated)
  const hydrateFromStorage = useAuthStore((state) => state.hydrateFromStorage)
  const setRedirectPath = useAuthStore((state) => state.setRedirectPath)

  useEffect(() => {
    hydrateFromStorage()
  }, [hydrateFromStorage])

  useEffect(() => {
    if (!hasHydrated || isAuthenticated) return

    const query = searchParams.toString()
    const redirectPath = query ? `${pathname}?${query}` : pathname
    setRedirectPath(redirectPath)
    router.replace("/login")
  }, [hasHydrated, isAuthenticated, pathname, router, searchParams, setRedirectPath])

  if (!hasHydrated || !isAuthenticated) {
    return <RouteFallback />
  }

  return <>{children}</>
}

export function AuthEntryRoute({ children }: GuardProps) {
  const router = useRouter()
  const hasHydrated = useAuthStore((state) => state.hasHydrated)
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated)
  const hydrateFromStorage = useAuthStore((state) => state.hydrateFromStorage)

  useEffect(() => {
    hydrateFromStorage()
  }, [hydrateFromStorage])

  useEffect(() => {
    if (hasHydrated && isAuthenticated) {
      router.replace("/dashboard")
    }
  }, [hasHydrated, isAuthenticated, router])

  if (!hasHydrated || isAuthenticated) {
    return <RouteFallback />
  }

  return <>{children}</>
}

function RouteFallback() {
  return <div className="min-h-screen bg-background" aria-label="加载中" />
}
