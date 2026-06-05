"use client"

import { usePathname } from "next/navigation"

import { AppShell } from "@/components/layout/app-shell"
import { ProtectedRoute } from "@/components/layout/protected-route"

interface AppFrameProps {
  children: React.ReactNode
}

export function AppFrame({ children }: AppFrameProps) {
  const pathname = usePathname()

  if (pathname === "/login") {
    return <>{children}</>
  }

  return (
    <ProtectedRoute>
      <AppShell>{children}</AppShell>
    </ProtectedRoute>
  )
}
