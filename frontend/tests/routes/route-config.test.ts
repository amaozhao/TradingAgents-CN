import { describe, expect, it } from "vitest"

import {
  getRouteByPath,
  menuRoutes,
  redirectRoutes,
  routeConfig
} from "@/libs/routes/route-config"

describe("route config", () => {
  it("keeps the current Vue URL surface", () => {
    const paths = routeConfig.map((route) => route.path)

    expect(paths).toEqual(
      expect.arrayContaining([
        "/dashboard",
        "/analysis/single",
        "/analysis/batch",
        "/screening",
        "/favorites",
        "/learning",
        "/learning/[category]",
        "/learning/article/[id]",
        "/stocks/[code]",
        "/tasks",
        "/reports",
        "/reports/view/[id]",
        "/reports/token",
        "/settings",
        "/settings/config",
        "/settings/database",
        "/settings/logs",
        "/settings/system-logs",
        "/settings/sync",
        "/settings/cache",
        "/settings/usage",
        "/settings/scheduler",
        "/login",
        "/about",
        "/paper"
      ])
    )
  })

  it("keeps known redirect compatibility rules", () => {
    expect(redirectRoutes).toContainEqual({
      source: "/queue",
      destination: "/tasks"
    })
    expect(redirectRoutes).toContainEqual({
      source: "/analysis/history",
      destination: "/tasks?tab=completed"
    })
    expect(redirectRoutes).toContainEqual({
      source: "/paper/[name].md",
      destination: "/learning/article/[name]"
    })
  })

  it("marks protected and public routes consistently with the Vue app", () => {
    expect(getRouteByPath("/dashboard")?.requiresAuth).toBe(true)
    expect(getRouteByPath("/reports/view/[id]")?.requiresAuth).toBe(true)
    expect(getRouteByPath("/settings/config")?.requiresAuth).toBe(true)
    expect(getRouteByPath("/learning")?.requiresAuth).toBe(false)
    expect(getRouteByPath("/about")?.requiresAuth).toBe(false)
    expect(getRouteByPath("/login")?.requiresAuth).toBe(false)
  })

  it("keeps primary sidebar entries and nested groups", () => {
    expect(menuRoutes.map((route) => route.path)).toEqual([
      "/dashboard",
      "/learning",
      "/analysis",
      "/tasks",
      "/screening",
      "/favorites",
      "/paper",
      "/settings",
      "/about"
    ])
    expect(menuRoutes.find((route) => route.path === "/analysis")?.children?.map((route) => route.path)).toEqual([
      "/analysis/single",
      "/analysis/batch",
      "/reports"
    ])
    expect(menuRoutes.find((route) => route.path === "/settings")?.children?.map((route) => route.title)).toEqual([
      "个人设置",
      "系统配置",
      "系统管理"
    ])
    expect(menuRoutes.find((route) => route.path === "/settings")?.children?.[0]?.children?.map((route) => route.title)).toEqual([
      "通用设置",
      "外观设置",
      "分析偏好",
      "通知设置",
      "安全设置"
    ])
    expect(menuRoutes.find((route) => route.path === "/settings")?.children?.[1]?.children?.map((route) => route.path)).toEqual([
      "/settings/config",
      "/settings/cache"
    ])
    expect(menuRoutes.find((route) => route.path === "/settings")?.children?.[2]?.children?.map((route) => route.path)).toEqual([
      "/settings/database",
      "/settings/logs",
      "/settings/system-logs",
      "/settings/sync",
      "/settings/scheduler",
      "/settings/usage"
    ])
  })
})
