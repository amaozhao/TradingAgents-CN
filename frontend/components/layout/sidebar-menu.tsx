"use client"

import Link from "next/link"
import { usePathname, useSearchParams } from "next/navigation"
import type { MouseEvent } from "react"
import { useState } from "react"

import type { AppRoute } from "@/libs/routes/route-config"
import { menuRoutes } from "@/libs/routes/route-config"
import { cn } from "@/libs/utils"

interface SidebarMenuProps {
  collapsed: boolean
  onNavigate?: (event: MouseEvent<HTMLAnchorElement>) => void
}

export function SidebarMenu({ collapsed, onNavigate }: SidebarMenuProps) {
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(() => new Set())

  const handleGroupToggle = (path: string) => {
    setExpandedGroups((previous) => {
      const next = new Set(previous)
      if (next.has(path)) {
        next.delete(path)
      } else {
        next.add(path)
      }
      return next
    })
  }

  return (
    <nav className="flex-1 overflow-y-auto p-2">
      <div className="space-y-1">
        {menuRoutes.map((route) => (
          <SidebarMenuItem
            key={route.path}
            route={route}
            collapsed={collapsed}
            expandedGroups={expandedGroups}
            onGroupToggle={handleGroupToggle}
            onNavigate={onNavigate}
          />
        ))}
      </div>
    </nav>
  )
}

function SidebarMenuItem({
  route,
  collapsed,
  expandedGroups,
  onGroupToggle,
  onNavigate
}: {
  route: AppRoute
  collapsed: boolean
  expandedGroups: Set<string>
  onGroupToggle: (path: string) => void
  onNavigate?: (event: MouseEvent<HTMLAnchorElement>) => void
}) {
  const pathname = usePathname()
  const searchParams = useSearchParams()
  const queryString = searchParams.toString()
  const currentPath = queryString ? `${pathname}?${queryString}` : pathname
  const Icon = route.icon
  const active = isRouteActive(route, pathname, currentPath)
  const expanded = active || expandedGroups.has(route.path)

  if (route.children?.length) {
    const groupHref = route.href || route.children[0]?.path || route.path

    return (
      <div className="space-y-1">
        <Link
          href={groupHref}
          aria-label={route.title}
          onClick={(event) => {
            onGroupToggle(route.path)
            onNavigate?.(event)
          }}
          className={cn(
            "flex h-9 items-center gap-2 rounded-md px-3 text-sm font-medium transition-colors hover:bg-sidebar-accent hover:text-sidebar-accent-foreground",
            active ? "text-sidebar-accent-foreground" : "text-sidebar-foreground"
          )}
        >
          {Icon ? <Icon className="size-4 shrink-0" /> : null}
          {!collapsed ? <span>{route.title}</span> : null}
        </Link>
        {!collapsed && expanded ? (
          <div className="ml-6 space-y-1 border-l pl-2">
            {route.children.map((child) => (
              <SidebarMenuItem
                key={child.path}
                route={child}
                collapsed={false}
                expandedGroups={expandedGroups}
                onGroupToggle={onGroupToggle}
                onNavigate={onNavigate}
              />
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
      onClick={onNavigate}
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

function isRouteActive(route: AppRoute, pathname: string, currentPath: string): boolean {
  const routePath = route.path.split("?")[0]
  const isQueryRoute = route.path.includes("?")
  const activePaths = route.activePaths ?? []

  if (activePaths.some((activePath) => (activePath.includes("?") ? currentPath === activePath : pathname === activePath))) return true
  if (isQueryRoute && currentPath === route.path) return true
  if (!isQueryRoute && pathname === routePath) {
    if (route.children?.length) return true
    if (routePath === "/settings") return currentPath === pathname
    return true
  }
  if (route.children?.length && pathname.startsWith(`${routePath}/`)) return true

  return route.children?.some((child) => isRouteActive(child, pathname, currentPath)) ?? false
}
