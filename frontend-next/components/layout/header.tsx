"use client"

import { Bell, HelpCircle, Maximize, Moon, Sun } from "lucide-react"
import { useTheme } from "next-themes"

import { Button } from "@/components/ui/button"
import { UserMenu } from "@/components/layout/user-menu"

export function HeaderActions() {
  const { resolvedTheme, setTheme } = useTheme()
  const isDark = resolvedTheme === "dark"

  return (
    <div className="flex items-center gap-1">
      <Button
        variant="ghost"
        size="icon"
        aria-label="切换主题"
        onClick={() => setTheme(isDark ? "light" : "dark")}
      >
        {isDark ? <Sun /> : <Moon />}
      </Button>
      <Button
        variant="ghost"
        size="icon"
        aria-label="全屏"
        onClick={() => {
          if (document.fullscreenElement) document.exitFullscreen()
          else document.documentElement.requestFullscreen()
        }}
      >
        <Maximize />
      </Button>
      <Button variant="ghost" size="icon" aria-label="通知">
        <Bell />
      </Button>
      <Button
        variant="ghost"
        size="icon"
        aria-label="帮助"
        onClick={() => window.open("https://mp.weixin.qq.com/s/ppsYiBncynxlsfKFG8uEbw", "_blank")}
      >
        <HelpCircle />
      </Button>
      <UserMenu />
    </div>
  )
}
