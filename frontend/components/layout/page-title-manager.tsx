"use client"

import { useEffect } from "react"
import { usePathname } from "next/navigation"

import { getRouteByPathname } from "@/libs/routes/route-config"

const appTitle = "AGENTrader"

export function PageTitleManager() {
  const pathname = usePathname()

  useEffect(() => {
    const route = getRouteByPathname(pathname)
    const title = route?.title ? `${route.title} - ${appTitle}` : appTitle
    const applyTitle = () => {
      if (document.title !== title) {
        document.title = title
      }
    }

    applyTitle()
    const frame = window.requestAnimationFrame(applyTitle)
    const timer = window.setTimeout(applyTitle, 250)
    const observer = new MutationObserver(applyTitle)
    observer.observe(document.head, { childList: true, subtree: true, characterData: true })

    return () => {
      window.cancelAnimationFrame(frame)
      window.clearTimeout(timer)
      observer.disconnect()
    }
  }, [pathname])

  return null
}
