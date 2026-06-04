"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"

import type { AppRoute } from "@/libs/routes/route-config"
import { menuRoutes } from "@/libs/routes/route-config"
import { cn } from "@/libs/utils"

interface SidebarMenuProps {
  collapsed: boolean
}

export function SidebarMenu({ collapsed }: SidebarMenuProps) {
  return (
    <nav className="flex-1 overflow-y-auto p-2">
      <div className="space-y-1">
        {menuRoutes.map((route) => (
          <SidebarMenuItem key={route.path} route={route} collapsed={collapsed} />
        ))}
      </div>
    </nav>
  )
}

function SidebarMenuItem({ route, collapsed }: { route: AppRoute; collapsed: boolean }) {
  const pathname = usePathname()
  const Icon = route.icon
  const active = pathname === route.path || pathname.startsWith(`${route.path}/`)

  if (route.children?.length) {
    return (
      <div className="space-y-1">
        <div className="flex h-9 items-center gap-2 rounded-md px-3 text-sm font-medium text-muted-foreground">
          {Icon ? <Icon className="size-4 shrink-0" /> : null}
          {!collapsed ? <span>{route.title}</span> : null}
        </div>
        {!collapsed ? (
          <div className="ml-6 space-y-1 border-l pl-2">
            {route.children.map((child) => (
              <SidebarMenuItem key={child.path} route={child} collapsed={false} />
            ))}
          </div>
        ) : null}
      </div>
    )
  }

  return (
    <Link
      href={route.path}
      aria-label={route.title}
      className={cn(
        "flex h-9 items-center gap-2 rounded-md px-3 text-sm transition-colors hover:bg-sidebar-accent hover:text-sidebar-accent-foreground",
        active ? "bg-sidebar-accent text-sidebar-accent-foreground" : "text-sidebar-foreground"
      )}
    >
      {Icon ? <Icon className="size-4 shrink-0" /> : null}
      {!collapsed ? <span className="truncate">{route.title}</span> : null}
    </Link>
  )
}
