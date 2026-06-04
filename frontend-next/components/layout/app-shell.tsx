"use client"

import { PanelLeftClose, PanelLeftOpen } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Breadcrumb } from "@/components/layout/breadcrumb"
import { Footer } from "@/components/layout/footer"
import { HeaderActions } from "@/components/layout/header"
import { NetworkStatus } from "@/components/layout/network-status"
import { Sidebar } from "@/components/layout/sidebar"
import { useAppStore } from "@/stores/app-store"
import { cn } from "@/libs/utils"

interface AppShellProps {
  children: React.ReactNode
}

export function AppShell({ children }: AppShellProps) {
  const sidebarCollapsed = useAppStore((state) => state.sidebarCollapsed)
  const setSidebarCollapsed = useAppStore((state) => state.setSidebarCollapsed)

  return (
    <div className="min-h-screen bg-muted/30 text-foreground">
      <Sidebar collapsed={sidebarCollapsed} />
      <NetworkStatus />

      <div className={cn("min-h-screen transition-[padding-left]", sidebarCollapsed ? "pl-16" : "pl-60")}>
        <header className="sticky top-0 z-30 flex h-14 items-center justify-between border-b bg-background px-4">
          <div className="flex min-w-0 items-center gap-2">
            <Button
              variant="ghost"
              size="icon"
              aria-label="切换侧边栏"
              onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
            >
              {sidebarCollapsed ? <PanelLeftOpen /> : <PanelLeftClose />}
            </Button>
            <Breadcrumb />
          </div>
          <HeaderActions />
        </header>
        <main className="mx-auto min-h-[calc(100vh-7rem)] w-full max-w-[1400px] p-6">{children}</main>
        <Footer />
      </div>
    </div>
  )
}
