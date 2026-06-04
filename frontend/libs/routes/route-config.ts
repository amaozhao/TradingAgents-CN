import type { LucideIcon } from "lucide-react"
import {
  BarChart3,
  BookOpen,
  ChartNoAxesCombined,
  ClipboardList,
  CreditCard,
  Database,
  FileText,
  History,
  Info,
  LayoutDashboard,
  ListChecks,
  ScrollText,
  Search,
  Settings,
  Star,
  Timer,
  Trash2
} from "lucide-react"

export interface AppRoute {
  path: string
  title: string
  icon?: LucideIcon
  requiresAuth: boolean
  hideInMenu?: boolean
  children?: AppRoute[]
}

export interface RedirectRoute {
  source: string
  destination: string
}

export const routeConfig: AppRoute[] = [
  { path: "/dashboard", title: "仪表板", icon: LayoutDashboard, requiresAuth: true },
  { path: "/analysis/single", title: "单股分析", icon: ChartNoAxesCombined, requiresAuth: true },
  { path: "/analysis/batch", title: "批量分析", icon: BarChart3, requiresAuth: true },
  { path: "/screening", title: "股票筛选", icon: Search, requiresAuth: true },
  { path: "/favorites", title: "我的自选股", icon: Star, requiresAuth: true },
  { path: "/learning", title: "学习中心", icon: BookOpen, requiresAuth: false },
  { path: "/learning/[category]", title: "学习分类", requiresAuth: false, hideInMenu: true },
  { path: "/learning/article/[id]", title: "文章详情", requiresAuth: false, hideInMenu: true },
  { path: "/stocks/[code]", title: "股票详情", icon: ChartNoAxesCombined, requiresAuth: true, hideInMenu: true },
  { path: "/tasks", title: "任务中心", icon: ListChecks, requiresAuth: true },
  { path: "/reports", title: "分析报告", icon: FileText, requiresAuth: true },
  { path: "/reports/view/[id]", title: "报告详情", requiresAuth: true, hideInMenu: true },
  { path: "/reports/token", title: "Token统计", requiresAuth: true, hideInMenu: true },
  { path: "/settings", title: "设置", icon: Settings, requiresAuth: true },
  { path: "/settings/config", title: "配置管理", icon: Settings, requiresAuth: true },
  { path: "/settings/database", title: "数据库管理", icon: Database, requiresAuth: true },
  { path: "/settings/logs", title: "操作日志", icon: History, requiresAuth: true },
  { path: "/settings/system-logs", title: "系统日志", icon: ScrollText, requiresAuth: true },
  { path: "/settings/sync", title: "多数据源同步", icon: ClipboardList, requiresAuth: true },
  { path: "/settings/cache", title: "缓存管理", icon: Trash2, requiresAuth: true },
  { path: "/settings/usage", title: "使用统计", icon: BarChart3, requiresAuth: true },
  { path: "/settings/scheduler", title: "定时任务", icon: Timer, requiresAuth: true },
  { path: "/login", title: "登录", requiresAuth: false, hideInMenu: true },
  { path: "/about", title: "关于", icon: Info, requiresAuth: false },
  { path: "/paper", title: "模拟交易", icon: CreditCard, requiresAuth: true }
]

export const menuRoutes: AppRoute[] = [
  getRequiredRoute("/dashboard"),
  getRequiredRoute("/learning"),
  {
    path: "/analysis",
    title: "股票分析",
    icon: ChartNoAxesCombined,
    requiresAuth: true,
    children: [
      getRequiredRoute("/analysis/single"),
      getRequiredRoute("/analysis/batch"),
      getRequiredRoute("/reports")
    ]
  },
  getRequiredRoute("/tasks"),
  getRequiredRoute("/screening"),
  getRequiredRoute("/favorites"),
  getRequiredRoute("/paper"),
  {
    path: "/settings",
    title: "设置",
    icon: Settings,
    requiresAuth: true,
    children: [
      getRequiredRoute("/settings"),
      getRequiredRoute("/settings/config"),
      getRequiredRoute("/settings/cache"),
      getRequiredRoute("/settings/database"),
      getRequiredRoute("/settings/logs"),
      getRequiredRoute("/settings/system-logs"),
      getRequiredRoute("/settings/sync"),
      getRequiredRoute("/settings/scheduler"),
      getRequiredRoute("/settings/usage")
    ]
  },
  getRequiredRoute("/about")
]

export const redirectRoutes: RedirectRoute[] = [
  { source: "/queue", destination: "/tasks" },
  { source: "/analysis/history", destination: "/tasks?tab=completed" },
  { source: "/paper/[name].md", destination: "/learning/article/[name]" }
]

export function getRouteByPath(path: string) {
  return routeConfig.find((route) => route.path === path)
}

export function getRouteByPathname(pathname: string) {
  return (
    routeConfig.find((route) => route.path === pathname) ||
    routeConfig.find((route) => {
      const pattern = route.path.replace(/\[[^\]]+\]/g, "[^/]+")
      return new RegExp(`^${pattern}$`).test(pathname)
    })
  )
}

function getRequiredRoute(path: string) {
  const route = getRouteByPath(path)
  if (!route) {
    throw new Error(`Missing route config for ${path}`)
  }
  return route
}
