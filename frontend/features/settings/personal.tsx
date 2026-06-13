"use client"

import { useRouter, useSearchParams } from "next/navigation"
import { useState, type ComponentProps } from "react"
import { useMutation } from "@tanstack/react-query"
import { Bell, Brush, Gauge, Loader2, Settings, Shield } from "lucide-react"
import { useTheme } from "next-themes"
import { toast } from "sonner"

import { PageHeader } from "@/components/feedback/page-header"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { authApi } from "@/libs/api/auth"
import { useAppStore, type AppLanguage, type AppTheme } from "@/stores/app-store"
import { useAuthStore } from "@/stores/auth-store"

type PersonalSettingsTab = "general" | "appearance" | "analysis" | "notifications" | "security"
const personalSettingsTabs: Array<{ value: PersonalSettingsTab; title: string }> = [
  { value: "general", title: "通用设置" },
  { value: "appearance", title: "外观设置" },
  { value: "analysis", title: "分析偏好" },
  { value: "notifications", title: "通知设置" },
  { value: "security", title: "安全设置" }
]

const personalTabValues = new Set<PersonalSettingsTab>(personalSettingsTabs.map((item) => item.value))

function getPersonalSettingsTab(value: string | null): PersonalSettingsTab {
  return value && personalTabValues.has(value as PersonalSettingsTab) ? (value as PersonalSettingsTab) : "general"
}

function getPersonalSettingsHref(tab: PersonalSettingsTab) {
  return tab === "general" ? "/settings" : `/settings?tab=${tab}`
}
function LoadingButton({ loading, children, ...props }: ComponentProps<typeof Button> & { loading?: boolean }) {
  return (
    <Button {...props} disabled={props.disabled || loading}>
      {loading ? <Loader2 className="mr-2 size-4 animate-spin" /> : null}
      {children}
    </Button>
  )
}

export function SettingsIndexPage() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const { setTheme: setDocumentTheme } = useTheme()
  const theme = useAppStore((state) => state.theme)
  const language = useAppStore((state) => state.language)
  const sidebarWidth = useAppStore((state) => state.sidebarWidth)
  const preferences = useAppStore((state) => state.preferences)
  const setTheme = useAppStore((state) => state.setTheme)
  const setLanguage = useAppStore((state) => state.setLanguage)
  const setSidebarWidth = useAppStore((state) => state.setSidebarWidth)
  const updatePreferences = useAppStore((state) => state.updatePreferences)
  const user = useAuthStore((state) => state.user)
  const userDisplayName = useAuthStore((state) => state.userDisplayName())
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated)
  const [passwordDialogOpen, setPasswordDialogOpen] = useState(false)
  const [passwordForm, setPasswordForm] = useState({
    old_password: "",
    new_password: "",
    confirm_password: ""
  })

  const activeTab = getPersonalSettingsTab(searchParams.get("tab"))

  const changePasswordMutation = useMutation({
    mutationFn: () => {
      if (passwordForm.new_password !== passwordForm.confirm_password) {
        throw new Error("两次输入的新密码不一致")
      }
      if (passwordForm.new_password.length < 8) {
        throw new Error("新密码至少需要 8 位")
      }
      return authApi.changePassword(passwordForm)
    },
    onSuccess: () => {
      toast.success("密码已修改")
      setPasswordDialogOpen(false)
      setPasswordForm({ old_password: "", new_password: "", confirm_password: "" })
    },
    onError: (error) => toast.error(error.message)
  })

  const handleTabChange = (value: string) => {
    router.replace(getPersonalSettingsHref(getPersonalSettingsTab(value)))
  }

  const handleThemeChange = (value: AppTheme) => {
    setTheme(value)
    setDocumentTheme(value === "auto" ? "system" : value)
  }

  return (
    <div className="space-y-6">
      <PageHeader title={personalSettingsTabs.find((item) => item.value === activeTab)?.title || "设置"} description="个性化配置和偏好设置" />

      <Tabs value={activeTab} onValueChange={handleTabChange} className="space-y-4">
        <TabsList className="flex h-auto flex-wrap justify-start">
          {personalSettingsTabs.map((item) => (
            <TabsTrigger key={item.value} value={item.value}>{item.title}</TabsTrigger>
          ))}
        </TabsList>

        <TabsContent value="general" className="mt-0">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <Settings className="size-4" />
                通用设置
              </CardTitle>
            </CardHeader>
            <CardContent className="grid max-w-2xl gap-5">
              <div className="space-y-2">
                <Label htmlFor="settings-username">用户名</Label>
                <Input id="settings-username" value={isAuthenticated ? userDisplayName : "未登录"} disabled />
              </div>
              <div className="space-y-2">
                <Label htmlFor="settings-email">邮箱</Label>
                <Input id="settings-email" value={user?.email || ""} placeholder="admin@trader.cn" readOnly />
              </div>
              <div className="space-y-2">
                <Label htmlFor="settings-language">语言</Label>
                <Select value={language} onValueChange={(value) => setLanguage(value as AppLanguage)}>
                  <SelectTrigger id="settings-language"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="zh-CN">简体中文</SelectItem>
                    <SelectItem value="en-US">English</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="settings-timezone">时区</Label>
                <Select value="Asia/Shanghai">
                  <SelectTrigger id="settings-timezone"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="Asia/Shanghai">北京时间 (UTC+8)</SelectItem>
                    <SelectItem value="America/New_York">纽约时间 (UTC-5)</SelectItem>
                    <SelectItem value="Europe/London">伦敦时间 (UTC+0)</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <Button type="button" className="w-fit" onClick={() => toast.success("设置已保存")}>保存设置</Button>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="appearance" className="mt-0">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <Brush className="size-4" />
                外观设置
              </CardTitle>
            </CardHeader>
            <CardContent className="grid max-w-2xl gap-5">
              <div className="space-y-2">
                <Label htmlFor="theme-mode">主题模式</Label>
                <div className="flex flex-wrap gap-2">
                  <Button type="button" variant={theme === "light" ? "default" : "outline"} onClick={() => handleThemeChange("light")}>浅色主题</Button>
                  <Button type="button" variant={theme === "dark" ? "default" : "outline"} onClick={() => handleThemeChange("dark")}>深色主题</Button>
                  <Button type="button" variant={theme === "auto" ? "default" : "outline"} onClick={() => handleThemeChange("auto")}>跟随系统</Button>
                </div>
              </div>
              <div className="space-y-2">
                <Label htmlFor="sidebar-width">侧边栏宽度</Label>
                <Input
                  id="sidebar-width"
                  min={200}
                  max={400}
                  type="number"
                  value={sidebarWidth}
                  onChange={(event) => setSidebarWidth(Number(event.target.value) || 240)}
                />
              </div>
              <Button type="button" className="w-fit" onClick={() => toast.success("设置已保存")}>保存设置</Button>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="analysis" className="mt-0">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <Gauge className="size-4" />
                分析偏好
              </CardTitle>
            </CardHeader>
            <CardContent className="grid max-w-2xl gap-5">
              <div className="space-y-2">
                <Label htmlFor="analysis-market">默认市场</Label>
                <Select value={preferences.defaultMarket} onValueChange={(value) => updatePreferences({ defaultMarket: value as "A股" | "美股" | "港股" })}>
                  <SelectTrigger id="analysis-market"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="A股">A股</SelectItem>
                    <SelectItem value="美股">美股</SelectItem>
                    <SelectItem value="港股">港股</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="default-depth">默认分析深度</Label>
                <Select value={preferences.defaultDepth} onValueChange={(value) => updatePreferences({ defaultDepth: value as "1" | "2" | "3" | "4" | "5" })}>
                  <SelectTrigger id="default-depth"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="1">1级 - 快速分析</SelectItem>
                    <SelectItem value="2">2级 - 基础分析</SelectItem>
                    <SelectItem value="3">3级 - 标准分析（推荐）</SelectItem>
                    <SelectItem value="4">4级 - 深度分析</SelectItem>
                    <SelectItem value="5">5级 - 全面分析</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>默认分析师</Label>
                <div className="grid gap-2 sm:grid-cols-2">
                  {["市场分析师", "基本面分析师", "新闻分析师", "社媒分析师"].map((analyst) => (
                    <label key={analyst} className="flex items-center gap-2 text-sm">
                      <input type="checkbox" defaultChecked />
                      {analyst}
                    </label>
                  ))}
                </div>
              </div>
              <label className="flex items-center gap-2 text-sm">
                <input type="checkbox" checked={preferences.autoRefresh} onChange={(event) => updatePreferences({ autoRefresh: event.target.checked })} />
                自动刷新
                <span className="text-muted-foreground">自动刷新分析结果</span>
              </label>
              <div className="space-y-2">
                <Label htmlFor="refresh-interval">刷新间隔</Label>
                <div className="flex items-center gap-2">
                  <Input
                    id="refresh-interval"
                    min={10}
                    max={300}
                    step={10}
                    type="number"
                    value={preferences.refreshInterval}
                    disabled={!preferences.autoRefresh}
                    onChange={(event) => updatePreferences({ refreshInterval: Number(event.target.value) || 30 })}
                  />
                  <span className="text-sm text-muted-foreground">秒</span>
                </div>
              </div>
              <Button type="button" className="w-fit" onClick={() => toast.success("设置已保存")}>保存设置</Button>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="notifications" className="mt-0">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <Bell className="size-4" />
                通知设置
              </CardTitle>
            </CardHeader>
            <CardContent className="grid max-w-2xl gap-5">
              <label className="flex items-center gap-2 text-sm">
                <input type="checkbox" defaultChecked />
                桌面通知
                <span className="text-muted-foreground">显示桌面通知</span>
              </label>
              <label className="flex items-center gap-2 text-sm">
                <input type="checkbox" defaultChecked />
                分析完成通知
              </label>
              <label className="flex items-center gap-2 text-sm">
                <input type="checkbox" defaultChecked />
                系统维护通知
              </label>
              <Button type="button" className="w-fit" onClick={() => toast.success("设置已保存")}>保存设置</Button>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="security" className="mt-0">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <Shield className="size-4" />
                安全设置
              </CardTitle>
            </CardHeader>
            <CardContent className="grid max-w-2xl gap-5">
              <div className="space-y-2">
                <Label>修改密码</Label>
                <Button type="button" onClick={() => setPasswordDialogOpen(true)}>修改密码</Button>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
      <Dialog open={passwordDialogOpen} onOpenChange={setPasswordDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>修改密码</DialogTitle>
            <DialogDescription>修改当前账号密码，保存后请使用新密码登录。</DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="grid gap-2">
              <Label htmlFor="old-password">当前密码</Label>
              <Input
                id="old-password"
                type="password"
                value={passwordForm.old_password}
                onChange={(event) => setPasswordForm((value) => ({ ...value, old_password: event.target.value }))}
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="new-password">新密码</Label>
              <Input
                id="new-password"
                type="password"
                value={passwordForm.new_password}
                onChange={(event) => setPasswordForm((value) => ({ ...value, new_password: event.target.value }))}
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="confirm-password">确认新密码</Label>
              <Input
                id="confirm-password"
                type="password"
                value={passwordForm.confirm_password}
                onChange={(event) => setPasswordForm((value) => ({ ...value, confirm_password: event.target.value }))}
              />
            </div>
            <LoadingButton
              loading={changePasswordMutation.isPending}
              onClick={() => changePasswordMutation.mutate()}
              disabled={!passwordForm.old_password || !passwordForm.new_password || !passwordForm.confirm_password}
            >
              保存
            </LoadingButton>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  )
}
