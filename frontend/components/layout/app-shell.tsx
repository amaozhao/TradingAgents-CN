"use client"

import { useState } from "react"
import Image from "next/image"
import { PanelLeftClose, PanelLeftOpen } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Breadcrumb } from "@/components/layout/breadcrumb"
import { Footer } from "@/components/layout/footer"
import { HeaderActions } from "@/components/layout/header"
import { NetworkStatus } from "@/components/layout/network-status"
import { Sidebar } from "@/components/layout/sidebar"
import { SidebarMenu } from "@/components/layout/sidebar-menu"
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet"
import { useAppStore } from "@/stores/app-store"
import { cn } from "@/libs/utils"

interface AppShellProps {
  children: React.ReactNode
}

export function AppShell({ children }: AppShellProps) {
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false)
  const sidebarCollapsed = useAppStore((state) => state.sidebarCollapsed)
  const setSidebarCollapsed = useAppStore((state) => state.setSidebarCollapsed)

  return (
    <div className="min-h-screen bg-muted/30 text-foreground">
      <Sidebar collapsed={sidebarCollapsed} />
      <Sheet open={mobileSidebarOpen} onOpenChange={setMobileSidebarOpen}>
        <SheetContent side="left" className="flex w-[280px] flex-col p-0">
          <SheetHeader className="border-b px-4 py-3 text-left">
            <SheetTitle className="flex items-center gap-2 text-sm">
              <Image src="/logo.svg" alt="TradingAgents-CN" width={32} height={32} className="size-8" />
              <span className="truncate">TradingAgents-CN</span>
            </SheetTitle>
            <SheetDescription className="sr-only">移动端主导航菜单</SheetDescription>
          </SheetHeader>
          <SidebarMenu collapsed={false} onNavigate={() => setMobileSidebarOpen(false)} />
        </SheetContent>
      </Sheet>
      <NetworkStatus />

      <div className={cn("min-h-screen transition-[padding-left] md:pl-60", sidebarCollapsed ? "md:pl-16" : "md:pl-60")}>
        <header className="sticky top-0 z-30 flex h-14 items-center justify-between border-b bg-background px-4">
          <div className="flex min-w-0 items-center gap-2">
            <Button
              variant="ghost"
              size="icon"
              className="md:hidden"
              aria-label="打开侧边栏"
              onClick={() => setMobileSidebarOpen(true)}
            >
              <PanelLeftOpen />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className="hidden md:inline-flex"
              aria-label="切换侧边栏"
              onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
            >
              {sidebarCollapsed ? <PanelLeftOpen /> : <PanelLeftClose />}
            </Button>
            <Breadcrumb />
          </div>
          <HeaderActions />
        </header>
        <main className="mx-auto min-h-[calc(100vh-7rem)] w-full max-w-[1400px] p-4 sm:p-6">{children}</main>
        <Footer />
      </div>
    </div>
  )
}
