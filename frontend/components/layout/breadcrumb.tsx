"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { ChevronRight, Home } from "lucide-react"

import { getRouteByPathname } from "@/libs/routes/route-config"

export function Breadcrumb() {
  const pathname = usePathname()
  const segments = pathname.split("/").filter(Boolean)

  if (!segments.length) {
    return null
  }

  const crumbs = segments.map((_, index) => {
    const path = `/${segments.slice(0, index + 1).join("/")}`
    const route = getRouteByPathname(path)
    return {
      href: path,
      title: route?.title ?? segments[index]
    }
  })

  return (
    <nav aria-label="面包屑" className="flex min-w-0 items-center gap-1 text-sm text-muted-foreground">
      <Link href="/dashboard" aria-label="首页" className="rounded-sm p-1 hover:text-foreground">
        <Home className="size-4" />
      </Link>
      {crumbs.map((crumb, index) => {
        const isLast = index === crumbs.length - 1

        return (
          <span key={crumb.href} className="flex min-w-0 items-center gap-1">
            <ChevronRight className="size-4 shrink-0" />
            {isLast ? (
              <span className="truncate text-foreground">{crumb.title}</span>
            ) : (
              <Link href={crumb.href} className="truncate hover:text-foreground">
                {crumb.title}
              </Link>
            )}
          </span>
        )
      })}
    </nav>
  )
}
