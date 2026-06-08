"use client"

import { useEffect } from "react"
import { usePathname } from "next/navigation"

import { getRouteByPathname } from "@/libs/routes/route-config"
import { useAppStore } from "@/stores/app-store"

const appTitle = "AGENTrader"

export function PageTitleManager() {
  const pathname = usePathname()
  const language = useAppStore((state) => state.language)

  useEffect(() => {
    const route = getRouteByPathname(pathname)
    const routeTitle = route?.titleI18n?.[language] || route?.title
    const title = routeTitle ? `${routeTitle} - ${appTitle}` : appTitle
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
  }, [language, pathname])

  return null
}
