"use client"

import Image from "next/image"

import { SidebarMenu } from "@/components/layout/sidebar-menu"
import { cn } from "@/libs/utils"

interface SidebarProps {
  collapsed: boolean
}

export function Sidebar({ collapsed }: SidebarProps) {
  return (
    <aside
      className={cn(
        "fixed inset-y-0 left-0 z-40 hidden flex-col border-r bg-sidebar transition-[width] md:flex",
        collapsed ? "w-16" : "w-60"
      )}
    >
      <div className="flex h-14 items-center gap-2 border-b px-4">
        <Image src="/logo.svg" alt="TradingAgents-CN" width={32} height={32} className="size-8" />
        {!collapsed ? <span className="truncate text-sm font-semibold">TradingAgents-CN</span> : null}
      </div>
      <SidebarMenu collapsed={collapsed} />
    </aside>
  )
}
