"use client"

import { useRouter, useSearchParams } from "next/navigation"
import { useEffect, useMemo, useState } from "react"
import { zodResolver } from "@hookform/resolvers/zod"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import type { EChartsOption } from "echarts"
import {
  AlertTriangle,
  Bell,
  Brush,
  Building2,
  CheckCircle2,
  Clock,
  CircleX,
  Cpu,
  Database,
  Download,
  Gauge,
  Info,
  Key,
  ListChecks,
  Loader2,
  Play,
  RefreshCw,
  Settings,
  Shield,
  Star,
  Trash2,
} from "lucide-react"
import { useTheme } from "next-themes"
import { useForm } from "react-hook-form"
import { toast } from "sonner"
import { z } from "zod"

import { EChartPanel } from "@/components/charts/e-chart-panel"
import { ConfirmDialog } from "@/components/feedback/confirm-dialog"
import { EmptyState } from "@/components/feedback/empty-state"
import { PageHeader } from "@/components/feedback/page-header"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import {
  cleanupOldCache,
  clearAllCache,
  getCacheBackendInfo,
  getCacheDetails,
  getCacheStats,
  type CacheDetailItem
} from "@/libs/api/cache"
import {
  configApi,
  type DataSourceConfig,
  type DatabaseConfig,
  type EnvConfigValidation,
  type LLMConfig,
  type LLMProvider,
  type PostgresConfigValidation,
  type SystemConfigValidation
} from "@/libs/api/config"
import { databaseApi, formatBytes, type DatabaseStatus } from "@/libs/api/database"
import { LogsApi, type LogFileInfo } from "@/libs/api/logs"
import { ActionTypes, getActionTypeName, OperationLogsApi, type OperationLog } from "@/libs/api/operation-logs"
import {
  getDataSourcesStatus,
  clearSyncCache,
  getSyncHistory,
  getSyncRecommendations,
  getSyncStatus,
  runStockBasicsSync,
  testDataSources,
  type DataSourceTestResult,
  type SyncStatus
} from "@/libs/api/sync"
import {
  cancelExecution,
  deleteExecution,
  getJobExecutions,
  getJobs,
  getSchedulerHealth,
  getSchedulerStats,
  markExecutionFailed,
  pauseJob,
  resumeJob,
  triggerJob,
  updateJobMetadata,
  type Job,
  type JobExecution
} from "@/libs/api/scheduler"
import { deleteOldRecords, getUsageRecords, getUsageStatistics, type UsageRecord } from "@/libs/api/usage"
import { formatDateTime } from "@/libs/utils/datetime"
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

const providerSchema = z.object({
  id: z.string().min(1, "请输入厂家 ID"),
  name: z.string().min(1, "请输入厂家名称"),
  display_name: z.string().min(1, "请输入显示名称"),
  default_base_url: z.string().optional(),
  api_key: z.string().optional(),
  description: z.string().optional()
})

type ProviderFormValues = z.infer<typeof providerSchema>

type ConfirmState = {
  title: string
  description: string
  confirmText?: string
  onConfirm: () => void
} | null

function boolBadge(value: boolean, trueText = "启用", falseText = "停用") {
  return <Badge variant={value ? "default" : "secondary"}>{value ? trueText : falseText}</Badge>
}

function StatCard({ label, value }: { label: string; value: string | number }) {
  return (
    <Card>
      <CardContent className="p-5">
        <div className="text-sm text-muted-foreground">{label}</div>
        <div className="mt-2 text-2xl font-semibold">{value}</div>
      </CardContent>
    </Card>
  )
}

function LoadingButton({ loading, children, ...props }: React.ComponentProps<typeof Button> & { loading?: boolean }) {
  return (
    <Button {...props} disabled={loading || props.disabled}>
      {loading ? <Loader2 className="mr-2 size-4 animate-spin" /> : null}
      {children}
    </Button>
  )
}

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const link = document.createElement("a")
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
}

function getResponseData<T>(response: { data: T }) {
  return response.data
}

function numberFrom(value: unknown, key: string): number {
  if (typeof value === "object" && value !== null && key in value) {
    const nextValue = (value as Record<string, unknown>)[key]
    return typeof nextValue === "number" ? nextValue : 0
  }
  return 0
}

function GenericTable<T>({
  rows,
  emptyText,
  children,
  tableClassName
}: {
  rows: T[]
  emptyText: string
  children: React.ReactNode
  tableClassName?: string
}) {
  return (
    <div className="overflow-x-auto rounded-md border">
      <Table className={tableClassName}>{children}</Table>
      {!rows.length ? <EmptyState title={emptyText} className="border-t p-8" /> : null}
    </div>
  )
}

const configTabs = [
  { value: "validation", label: "配置验证", icon: CheckCircle2 },
  { value: "providers", label: "厂家管理", icon: Building2 },
  { value: "model-catalog", label: "模型目录", icon: ListChecks },
  { value: "llm", label: "大模型配置", icon: Cpu },
  { value: "datasource", label: "数据源配置", icon: Gauge },
  { value: "database", label: "数据库配置", icon: Database },
  { value: "system", label: "系统设置", icon: Settings },
  { value: "api-keys", label: "API密钥状态", icon: Key },
  { value: "import-export", label: "导入导出", icon: Download }
] as const

type ConfigTabValue = (typeof configTabs)[number]["value"]

const requiredConfigItems = [
  { key: "POSTGRES_HOST", name: "PostgreSQL 主机", description: "PostgreSQL 数据库主机地址" },
  { key: "POSTGRES_PORT", name: "PostgreSQL 端口", description: "PostgreSQL 数据库端口" },
  { key: "POSTGRES_DB", name: "PostgreSQL 数据库", description: "PostgreSQL 数据库名称" },
  { key: "REDIS_HOST", name: "Redis 主机", description: "Redis 缓存主机地址" },
  { key: "REDIS_PORT", name: "Redis 端口", description: "Redis 缓存端口" },
  { key: "JWT_SECRET", name: "JWT 密钥", description: "JWT 认证密钥" }
] as const

const recommendedConfigItems = [
  { key: "AIHUBMIX_API_KEY", name: "AIHubMix API", description: "AIHubMix API 密钥", help: "用于 AI 分析功能" },
  { key: "DEEPSEEK_API_KEY", name: "DeepSeek API", description: "DeepSeek 大模型 API 密钥", help: "用于 AI 分析功能" },
  { key: "DASHSCOPE_API_KEY", name: "通义千问 API", description: "阿里云通义千问 API 密钥", help: "用于 AI 分析功能" },
  { key: "TUSHARE_TOKEN", name: "Tushare Token", description: "Tushare 数据源 Token", help: "用于获取专业A股数据" }
] as const

function StatusBadge({ configured, warningText }: { configured: boolean; warningText?: string }) {
  const text = warningText || (configured ? "已配置" : "未配置")
  return (
    <Badge variant={configured ? "default" : "secondary"} className={configured ? "" : "bg-amber-100 text-amber-800 hover:bg-amber-100"}>
      {text}
    </Badge>
  )
}

function ConfigStatusItem({
  title,
  description,
  configured,
  help,
  status
}: {
  title: string
  description: string
  configured: boolean
  help?: string
  status?: string
}) {
  const Icon = configured ? CheckCircle2 : AlertTriangle
  return (
    <div className="flex items-start gap-3 rounded-md border p-3">
      <Icon className={configured ? "mt-0.5 size-5 text-emerald-600" : "mt-0.5 size-5 text-amber-600"} />
      <div className="min-w-0 flex-1">
        <div className="font-medium">{title}</div>
        <div className="mt-1 text-sm text-muted-foreground">{description}</div>
        {help ? <div className="mt-1 text-xs text-muted-foreground">{help}</div> : null}
      </div>
      <StatusBadge configured={configured} warningText={status} />
    </div>
  )
}

function ValidationSummary({ validation }: { validation?: SystemConfigValidation }) {
  if (!validation) {
    return <EmptyState title="正在加载配置验证结果" className="rounded-md border p-8" />
  }

  const envValidation = validation.env_validation
  const postgresValidation = validation.postgres_validation
  const missingRequired = envValidation?.missing_required?.length || 0
  const invalidConfigs = envValidation?.invalid_configs?.length || 0
  const missingRecommended = envValidation?.missing_recommended?.length || 0
  const postgresWarnings = postgresValidation?.warnings?.length || 0
  const hasWarnings = missingRecommended > 0 || postgresWarnings > 0

  if (!validation.success) {
    return (
      <div className="rounded-md border border-destructive/30 bg-destructive/10 p-4">
        <div className="flex items-center gap-2 font-medium text-destructive"><CircleX className="size-5" />配置验证失败</div>
        {missingRequired ? <p className="mt-2 text-sm">缺少 {missingRequired} 个必需配置</p> : null}
        {invalidConfigs ? <p className="mt-1 text-sm">{invalidConfigs} 个配置无效</p> : null}
      </div>
    )
  }

  if (hasWarnings) {
    return (
      <div className="rounded-md border border-amber-300 bg-amber-50 p-4 text-amber-900">
        <div className="flex items-center gap-2 font-medium"><AlertTriangle className="size-5" />配置验证通过（有推荐配置未设置）</div>
        {missingRecommended ? <p className="mt-2 text-sm">缺少 {missingRecommended} 个推荐配置</p> : null}
        {postgresWarnings ? <p className="mt-1 text-sm">{postgresWarnings} 个 PostgreSQL 配置警告</p> : null}
      </div>
    )
  }

  return (
    <div className="rounded-md border border-emerald-300 bg-emerald-50 p-4 text-emerald-900">
      <div className="flex items-center gap-2 font-medium"><CheckCircle2 className="size-5" />配置验证通过</div>
      <p className="mt-2 text-sm">所有配置已正确设置</p>
    </div>
  )
}

function ConfigValidationPanel({
  validation,
  validating,
  onValidate
}: {
  validation?: SystemConfigValidation
  validating: boolean
  onValidate: () => void
}) {
  const envValidation: EnvConfigValidation | undefined = validation?.env_validation
  const postgresValidation: PostgresConfigValidation | undefined = validation?.postgres_validation

  const requiredRows = requiredConfigItems.map((item) => {
    const missing = envValidation?.missing_required?.find((config) => config.key === item.key)
    const invalid = envValidation?.invalid_configs?.find((config) => config.key === item.key)
    return { ...item, configured: !missing && !invalid, error: invalid?.error || (missing ? "未配置" : undefined) }
  })
  const recommendedRows = recommendedConfigItems.map((item) => {
    const missing = envValidation?.missing_recommended?.find((config) => config.key === item.key)
    return { ...item, configured: !missing }
  })

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle className="flex items-center gap-2"><CheckCircle2 className="size-5" />配置验证</CardTitle>
        <LoadingButton variant="outline" size="sm" loading={validating} onClick={onValidate}>重新验证</LoadingButton>
      </CardHeader>
      <CardContent className="space-y-6">
        <ValidationSummary validation={validation} />

        <section className="space-y-3">
          <h3 className="flex items-center gap-2 text-sm font-semibold"><Star className="size-4" />必需配置</h3>
          <div className="space-y-3">
            {requiredRows.map((item) => (
              <ConfigStatusItem key={item.key} title={item.name} description={item.description} configured={item.configured} status={item.error} />
            ))}
          </div>
        </section>

        <section className="space-y-3">
          <h3 className="flex items-center gap-2 text-sm font-semibold"><AlertTriangle className="size-4" />推荐配置</h3>
          <div className="space-y-3">
            {recommendedRows.map((item) => (
              <ConfigStatusItem key={item.key} title={item.name} description={item.description} configured={item.configured} help={item.help} />
            ))}
          </div>
        </section>

        {postgresValidation ? (
          <section className="space-y-4">
            <h3 className="flex items-center gap-2 text-sm font-semibold"><Database className="size-4" />PostgreSQL 配置验证</h3>
            {postgresValidation.llm_providers?.length ? (
              <div className="space-y-3">
                <div className="text-sm font-medium">大模型厂家</div>
                {postgresValidation.llm_providers.map((item) => (
                  <ConfigStatusItem key={item.name} title={item.display_name} description={item.name} configured={item.status.includes("已配置")} status={item.status} />
                ))}
              </div>
            ) : null}
            {postgresValidation.data_source_configs?.length ? (
              <div className="space-y-3">
                <div className="text-sm font-medium">数据源配置</div>
                {postgresValidation.data_source_configs.map((item) => (
                  <ConfigStatusItem key={item.name} title={item.name} description={item.type} configured={item.status.includes("已配置")} status={item.status} />
                ))}
              </div>
            ) : null}
            {postgresValidation.warnings?.length ? (
              <div className="space-y-2">
                {postgresValidation.warnings.map((warning, index) => (
                  <div key={`${warning}-${index}`} className="rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">{warning}</div>
                ))}
              </div>
            ) : null}
          </section>
        ) : null}

        {envValidation?.warnings?.length ? (
          <section className="space-y-2">
            <h3 className="flex items-center gap-2 text-sm font-semibold"><Info className="size-4" />环境变量警告</h3>
            {envValidation.warnings.map((warning, index) => (
              <div key={`${warning}-${index}`} className="rounded-md border p-3 text-sm text-muted-foreground">{warning}</div>
            ))}
          </section>
        ) : null}

        <section className="rounded-md border p-4">
          <h3 className="text-sm font-semibold">如何修复配置问题？</h3>
          <div className="mt-3 space-y-2 text-sm text-muted-foreground">
            <p>必需配置需要在 .env 文件中设置，保存后重启后端服务才能生效。</p>
            <p>推荐配置可以在 .env 中设置，也可以在厂家管理、大模型配置或数据源配置中维护。</p>
          </div>
        </section>
      </CardContent>
    </Card>
  )
}

function ApiKeyStatusPanel({
  providers,
  llmConfigs,
  onRefresh,
  onConfigure,
  onMigrate,
  loading
}: {
  providers: LLMProvider[]
  llmConfigs: LLMConfig[]
  onRefresh: () => void
  onConfigure: (provider: LLMProvider) => void
  onMigrate: () => void
  loading: boolean
}) {
  const configuredProviders = providers.filter((provider) => provider.extra_config?.has_api_key).length
  const activeProviders = providers.filter((provider) => provider.is_active).length

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle>API密钥状态</CardTitle>
        <LoadingButton variant="outline" size="sm" loading={loading} onClick={onRefresh}>刷新状态</LoadingButton>
      </CardHeader>
      <CardContent className="space-y-6">
        <div className="grid gap-6 lg:grid-cols-2">
          <section className="space-y-3">
            <h3 className="text-sm font-semibold">AI厂家密钥状态</h3>
            {providers.length ? providers.map((provider) => (
              <div key={provider.id} className="flex items-center gap-3 rounded-md border p-3">
                <Key className="size-4 text-muted-foreground" />
                <div className="min-w-0 flex-1 font-medium">{provider.display_name || provider.name}</div>
                <Badge variant={provider.extra_config?.has_api_key ? "default" : "destructive"}>
                  {provider.extra_config?.has_api_key ? provider.extra_config.source === "environment" ? "环境变量" : "已配置" : "未配置"}
                </Badge>
                {!provider.extra_config?.has_api_key ? <Button variant="outline" size="sm" onClick={() => onConfigure(provider)}>配置</Button> : null}
              </div>
            )) : (
              <EmptyState title="暂无厂家配置" className="rounded-md border p-8" />
            )}
          </section>

          <section className="space-y-3">
            <h3 className="text-sm font-semibold">配置统计</h3>
            <div className="grid gap-3 sm:grid-cols-2">
              <StatCard label="总厂家数" value={providers.length} />
              <StatCard label="已配置密钥" value={configuredProviders} />
              <StatCard label="启用厂家" value={activeProviders} />
              <StatCard label="配置模型" value={llmConfigs.length} />
            </div>
          </section>
        </div>

        <div className="grid gap-4 lg:grid-cols-3">
          <Card>
            <CardHeader><CardTitle className="text-sm">如何配置API密钥？</CardTitle></CardHeader>
            <CardContent className="space-y-2 text-sm text-muted-foreground">
              <p>在厂家管理中添加或编辑 AI 厂家，填入 API 密钥后，大模型配置会自动使用厂家密钥。</p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader><CardTitle className="text-sm">从环境变量迁移</CardTitle></CardHeader>
            <CardContent className="space-y-3">
              <p className="text-sm text-muted-foreground">如果 .env 已配置密钥，可以一键迁移到厂家管理。</p>
              <Button size="sm" onClick={onMigrate}>迁移环境变量</Button>
            </CardContent>
          </Card>
          <Card>
            <CardHeader><CardTitle className="text-sm">安全提示</CardTitle></CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground">敏感密钥通过环境变量或运维配置注入，后端响应会脱敏；请勿在导出文件中保存真实密钥。</p>
            </CardContent>
          </Card>
        </div>
      </CardContent>
    </Card>
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

  const activeTab = getPersonalSettingsTab(searchParams.get("tab"))

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
                <Button type="button" onClick={() => toast.info("修改密码功能将使用账户接口处理")}>修改密码</Button>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}

export function ConfigManagementPage() {
  const queryClient = useQueryClient()
  const [open, setOpen] = useState(false)
  const [confirm, setConfirm] = useState<ConfirmState>(null)
  const [activeTab, setActiveTab] = useState<ConfigTabValue>("validation")
  const [editingProvider, setEditingProvider] = useState<LLMProvider | null>(null)
  const [modelDialogOpen, setModelDialogOpen] = useState(false)
  const [dataSourceDialogOpen, setDataSourceDialogOpen] = useState(false)
  const [editingDataSourceName, setEditingDataSourceName] = useState<string | null>(null)
  const [marketDialogOpen, setMarketDialogOpen] = useState(false)
  const [groupingDialogOpen, setGroupingDialogOpen] = useState(false)
  const [databaseDialogOpen, setDatabaseDialogOpen] = useState(false)
  const [editingDatabaseName, setEditingDatabaseName] = useState<string | null>(null)
  const [settingsDraft, setSettingsDraft] = useState<Record<string, unknown>>({})
  const [configImportFile, setConfigImportFile] = useState<File | null>(null)
  const [modelForm, setModelForm] = useState({ provider: "", provider_name: "", model_name: "" })
  const [dataSourceForm, setDataSourceForm] = useState({ name: "", type: "stock", display_name: "", priority: 1 })
  const [marketForm, setMarketForm] = useState({ id: "", name: "", display_name: "", sort_order: 1 })
  const [groupingForm, setGroupingForm] = useState({ data_source_name: "", market_category_id: "", priority: 1 })
  const [databaseForm, setDatabaseForm] = useState({
    name: "",
    type: "postgresql",
    host: "localhost",
    port: 5432,
    username: "",
    password: "",
    database: "",
    pool_size: 5,
    max_overflow: 10,
    enabled: true,
    description: ""
  })

  const providersQuery = useQuery({ queryKey: ["config", "llm-providers"], queryFn: () => configApi.getLLMProviders(), retry: false })
  const llmQuery = useQuery({ queryKey: ["config", "llm"], queryFn: () => configApi.getLLMConfigs(), retry: false })
  const dataSourceQuery = useQuery({ queryKey: ["config", "datasources"], queryFn: () => configApi.getDataSourceConfigs(), retry: false })
  const marketQuery = useQuery({ queryKey: ["config", "market-categories"], queryFn: () => configApi.getMarketCategories(), retry: false })
  const databaseQuery = useQuery({ queryKey: ["config", "database"], queryFn: () => configApi.getDatabaseConfigs(), retry: false })
  const settingsQuery = useQuery({ queryKey: ["config", "settings"], queryFn: () => configApi.getSystemSettings(), retry: false })
  const settingsMetaQuery = useQuery({ queryKey: ["config", "settings-meta"], queryFn: () => configApi.getSystemSettingsMeta(), retry: false })
  const modelCatalogQuery = useQuery({ queryKey: ["config", "model-catalog"], queryFn: () => configApi.getModelCatalog(), retry: false })
  const groupingsQuery = useQuery({ queryKey: ["config", "datasource-groupings"], queryFn: () => configApi.getDataSourceGroupings(), retry: false })
  const validationQuery = useQuery({ queryKey: ["config", "validation"], queryFn: () => configApi.validateSystemConfig(), retry: false })

  const form = useForm<ProviderFormValues>({
    resolver: zodResolver(providerSchema),
    defaultValues: {
      id: "",
      name: "",
      display_name: "",
      default_base_url: "",
      api_key: "",
      description: ""
    }
  })

  const refreshConfig = () => {
    void queryClient.invalidateQueries({ queryKey: ["config"] })
  }

  const saveProviderMutation = useMutation({
    mutationFn: (values: ProviderFormValues) => {
      const payload = values as Partial<LLMProvider> & { api_key?: string }
      return editingProvider ? configApi.updateLLMProvider(editingProvider.id, payload) : configApi.addLLMProvider(payload)
    },
    onSuccess: () => {
      toast.success("厂家已保存")
      setOpen(false)
      setEditingProvider(null)
      form.reset()
      refreshConfig()
    },
    onError: (error) => toast.error(error.message)
  })

  const actionMutation = useMutation({
    mutationFn: async (action: () => Promise<unknown>) => action(),
    onSuccess: () => {
      toast.success("操作已完成")
      refreshConfig()
    },
    onError: (error) => toast.error(error.message)
  })

  const providers = providersQuery.data || []
  const llmConfigs = useMemo(() => llmQuery.data || [], [llmQuery.data])
  const dataSources = dataSourceQuery.data || []
  const marketCategories = marketQuery.data || []
  const databases = databaseQuery.data || []
  const settings = useMemo(() => settingsQuery.data || {}, [settingsQuery.data])
  const catalog = modelCatalogQuery.data || []
  const groupings = groupingsQuery.data || []
  const settingsMeta = useMemo(() => settingsMetaQuery.data?.items || [], [settingsMetaQuery.data])
  const settingsMetaMap = useMemo(() => new Map(settingsMeta.map((item) => [item.key, item])), [settingsMeta])
  const settingsValues = useMemo(() => ({ ...settings, ...settingsDraft }), [settings, settingsDraft])

  const providerModelCount = useMemo(() => {
    const counts = new Map<string, number>()
    llmConfigs.forEach((item) => counts.set(item.provider, (counts.get(item.provider) || 0) + 1))
    return counts
  }, [llmConfigs])

  const openAddProviderDialog = () => {
    setEditingProvider(null)
    form.reset({ id: "", name: "", display_name: "", default_base_url: "", api_key: "", description: "" })
    setOpen(true)
  }

  const openEditProviderDialog = (provider: LLMProvider) => {
    setEditingProvider(provider)
    form.reset({
      id: provider.id,
      name: provider.name,
      display_name: provider.display_name,
      default_base_url: provider.default_base_url || "",
      api_key: "",
      description: provider.description || ""
    })
    setOpen(true)
  }

  const openAddDataSourceDialog = () => {
    setEditingDataSourceName(null)
    setDataSourceForm({ name: "", type: "stock", display_name: "", priority: 1 })
    setDataSourceDialogOpen(true)
  }

  const openEditDataSourceDialog = (source: DataSourceConfig) => {
    setEditingDataSourceName(source.name)
    setDataSourceForm({
      name: source.name,
      type: source.type,
      display_name: source.display_name || "",
      priority: source.priority
    })
    setDataSourceDialogOpen(true)
  }

  const defaultDatabaseForm = () => ({
    name: "",
    type: "postgresql",
    host: "localhost",
    port: 5432,
    username: "",
    password: "",
    database: "",
    pool_size: 5,
    max_overflow: 10,
    enabled: true,
    description: ""
  })

  const openAddDatabaseDialog = () => {
    setEditingDatabaseName(null)
    setDatabaseForm(defaultDatabaseForm())
    setDatabaseDialogOpen(true)
  }

  const openEditDatabaseDialog = (database: DatabaseConfig) => {
    setEditingDatabaseName(database.name)
    setDatabaseForm({
      name: database.name,
      type: database.type,
      host: database.host,
      port: database.port,
      username: database.username || "",
      password: "",
      database: database.database || "",
      pool_size: database.pool_size,
      max_overflow: database.max_overflow,
      enabled: database.enabled,
      description: database.description || ""
    })
    setDatabaseDialogOpen(true)
  }

  const updateSettingDraft = (key: string, value: unknown) => {
    setSettingsDraft((previous) => ({ ...previous, [key]: value }))
  }

  const parseImportFile = async (file: File) => JSON.parse(await file.text()) as Record<string, unknown>

  return (
    <div>
      <PageHeader
        title="配置管理"
        description="管理系统配置、大模型、数据源等设置"
        actions={
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" onClick={() => actionMutation.mutate(() => configApi.reloadConfig())}>重载配置</Button>
          </div>
        }
      />

      <Tabs value={activeTab} onValueChange={(value) => setActiveTab(value as ConfigTabValue)} className="space-y-4">
        <TabsList className="flex h-auto flex-wrap justify-start">
          {configTabs.map((item) => {
            const Icon = item.icon
            return (
              <TabsTrigger key={item.value} value={item.value} className="gap-2">
                <Icon className="size-4" />
                {item.label}
              </TabsTrigger>
            )
          })}
        </TabsList>

        <TabsContent value="validation" className="mt-0">
          <ConfigValidationPanel
            validation={validationQuery.data}
            validating={validationQuery.isFetching}
            onValidate={() => void validationQuery.refetch()}
          />
        </TabsContent>

        <TabsContent value="providers" className="mt-0">
          <Card>
            <CardHeader className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <CardTitle>大模型厂家管理</CardTitle>
              <div className="flex flex-wrap gap-2">
                <Button size="sm" onClick={openAddProviderDialog}>添加厂家</Button>
                <Button variant="outline" size="sm" onClick={() => actionMutation.mutate(() => configApi.migrateEnvToProviders())}>迁移环境变量</Button>
                <Button variant="outline" size="sm" onClick={() => actionMutation.mutate(() => configApi.initAggregatorProviders())}>初始化聚合渠道</Button>
              </div>
            </CardHeader>
            <CardContent>
              <GenericTable<LLMProvider> rows={providers} emptyText="暂无厂家配置" tableClassName="min-w-[1100px] table-fixed">
                <colgroup>
                  <col className="w-[180px]" />
                  <col className="w-[108px]" />
                  <col className="w-[360px]" />
                  <col className="w-[108px]" />
                  <col className="w-[180px]" />
                  <col className="w-[260px]" />
                </colgroup>
                <TableHeader>
                  <TableRow>
                    <TableHead>厂家信息</TableHead>
                    <TableHead className="whitespace-nowrap">API密钥</TableHead>
                    <TableHead>描述</TableHead>
                    <TableHead className="whitespace-nowrap">状态</TableHead>
                    <TableHead>支持功能</TableHead>
                    <TableHead className="whitespace-nowrap text-right">操作</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {providers.map((provider) => (
                    <TableRow key={provider.id}>
                      <TableCell className="pr-6">
                        <div className="font-medium">{provider.display_name || provider.name}</div>
                        <div className="text-xs text-muted-foreground">{provider.name}</div>
                      </TableCell>
                      <TableCell className="whitespace-nowrap">{provider.extra_config?.has_api_key ? "已配置" : "未配置"}</TableCell>
                      <TableCell><div className="line-clamp-2 text-sm text-muted-foreground">{provider.description || "暂无描述"}</div></TableCell>
                      <TableCell className="whitespace-nowrap">
                        <div className="flex flex-col items-start gap-1">
                          {boolBadge(provider.is_active, "启用", "禁用")}
                          {provider.extra_config?.has_api_key ? <Badge variant="secondary">{provider.extra_config.source === "environment" ? "ENV" : "DB"}</Badge> : null}
                        </div>
                      </TableCell>
                      <TableCell>
                        <div className="flex flex-wrap gap-1">
                          {provider.supported_features?.length ? provider.supported_features.map((feature, index) => <Badge key={`${feature}-${index}`} variant="secondary">{feature}</Badge>) : <span className="text-sm text-muted-foreground">-</span>}
                        </div>
                        <div className="mt-1 text-xs text-muted-foreground">模型数：{providerModelCount.get(provider.name) || 0}</div>
                      </TableCell>
                      <TableCell className="whitespace-nowrap">
                        <div className="flex justify-end gap-2">
                          <Button variant="outline" size="sm" aria-label={`编辑 ${provider.name}`} onClick={() => openEditProviderDialog(provider)}>编辑</Button>
                          <Button variant="outline" size="sm" onClick={() => actionMutation.mutate(() => configApi.testProviderAPI(provider.id))}>测试</Button>
                          <Button variant="outline" size="sm" onClick={() => actionMutation.mutate(() => configApi.toggleLLMProvider(provider.id, !provider.is_active))}>
                            {provider.is_active ? "停用" : "启用"}
                          </Button>
                          <Button
                            variant="destructive"
                            size="sm"
                            onClick={() => setConfirm({
                              title: "删除厂家",
                              description: `确定要删除厂家 ${provider.display_name || provider.name} 吗？相关模型配置也会受影响。`,
                              confirmText: "删除",
                              onConfirm: () => actionMutation.mutate(() => configApi.deleteLLMProvider(provider.id))
                            })}
                          >
                            删除
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </GenericTable>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="model-catalog" className="mt-0">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle>模型目录</CardTitle>
              <div className="flex gap-2">
                <Button variant="outline" size="sm" onClick={() => setModelDialogOpen(true)}>新增模型目录</Button>
                <Button variant="outline" size="sm" onClick={() => actionMutation.mutate(() => configApi.initModelCatalog())}>初始化模型目录</Button>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              {catalog.length ? (
                <div className="grid gap-4 md:grid-cols-2">
                  {catalog.map((item) => (
                    <div key={item.provider} className="rounded-md border p-4">
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <div className="font-medium">{item.provider_name}</div>
                          <div className="mt-1 text-sm text-muted-foreground">{item.provider} / {item.models.length} 个模型</div>
                        </div>
                        <Button
                          variant="destructive"
                          size="sm"
                          onClick={() => setConfirm({
                            title: "删除模型目录",
                            description: `确定要删除 ${item.provider_name} 的模型目录吗？`,
                            confirmText: "删除",
                            onConfirm: () => actionMutation.mutate(() => configApi.deleteModelCatalog(item.provider))
                          })}
                        >
                          删除
                        </Button>
                      </div>
                      <div className="mt-4 flex flex-wrap gap-2">
                        {item.models.slice(0, 12).map((model, index) => <Badge key={`${model.name}-${index}`} variant="secondary">{model.display_name || model.name}</Badge>)}
                        {item.models.length > 12 ? <Badge variant="outline">+{item.models.length - 12}</Badge> : null}
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <EmptyState title="暂无模型目录" className="rounded-md border p-8" />
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="llm" className="mt-0">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle>大模型配置</CardTitle>
              <div className="flex gap-2">
                <Button variant="outline" size="sm" onClick={() => setModelDialogOpen(true)}>添加模型</Button>
              </div>
            </CardHeader>
            <CardContent className="space-y-6">
              <GenericTable<LLMConfig> rows={llmConfigs} emptyText="暂无模型配置">
                <TableHeader>
                  <TableRow>
                    <TableHead>模型</TableHead>
                    <TableHead>厂家</TableHead>
                    <TableHead>参数</TableHead>
                    <TableHead>状态</TableHead>
                    <TableHead>操作</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {llmConfigs.map((config) => (
                    <TableRow key={`${config.provider}-${config.model_name}`}>
                      <TableCell>
                        <div className="font-medium">{config.model_display_name || config.model_name}</div>
                        <div className="text-xs text-muted-foreground">{config.model_name}</div>
                      </TableCell>
                      <TableCell>{config.provider}</TableCell>
                      <TableCell className="text-xs text-muted-foreground">tokens {config.max_tokens} / temp {config.temperature}</TableCell>
                      <TableCell>{boolBadge(config.enabled)}</TableCell>
                      <TableCell>
                        <div className="flex flex-wrap gap-2">
                          <Button
                            variant="outline"
                            size="sm"
                            aria-label={`测试模型 ${config.model_name}`}
                            onClick={() => actionMutation.mutate(() => configApi.testConfig({ config_type: "llm", config_data: config as unknown as Record<string, unknown> }))}
                          >
                            测试
                          </Button>
                          <Button variant="outline" size="sm" onClick={() => actionMutation.mutate(() => configApi.setDefaultLLM(config.model_name))}>设为默认</Button>
                          <Button variant="outline" size="sm" onClick={() => actionMutation.mutate(() => configApi.updateLLMConfig({ ...config, enabled: !config.enabled }))}>
                            {config.enabled ? "停用" : "启用"}
                          </Button>
                          <Button
                            variant="destructive"
                            size="sm"
                            onClick={() => setConfirm({
                              title: "删除模型配置",
                              description: `确定要删除 ${config.provider}/${config.model_name} 吗？`,
                              confirmText: "删除",
                              onConfirm: () => actionMutation.mutate(() => configApi.deleteLLMConfig(config.provider, config.model_name))
                            })}
                          >
                            删除
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </GenericTable>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="datasource" className="mt-0 space-y-4">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle>数据源配置</CardTitle>
              <Button variant="outline" size="sm" onClick={openAddDataSourceDialog}>新增数据源</Button>
            </CardHeader>
            <CardContent>
              <GenericTable<DataSourceConfig> rows={dataSources} emptyText="暂无数据源配置">
                <TableHeader>
                  <TableRow>
                    <TableHead>数据源</TableHead>
                    <TableHead>类型</TableHead>
                    <TableHead>优先级</TableHead>
                    <TableHead>市场</TableHead>
                    <TableHead>状态</TableHead>
                    <TableHead>操作</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {dataSources.map((source) => (
                    <TableRow key={source.name}>
                      <TableCell>
                        <div className="font-medium">{source.display_name || source.name}</div>
                        <div className="text-xs text-muted-foreground">{source.description || source.endpoint || "暂无描述"}</div>
                      </TableCell>
                      <TableCell>{source.type}</TableCell>
                      <TableCell>{source.priority}</TableCell>
                      <TableCell>{source.market_categories?.join(", ") || "-"}</TableCell>
                      <TableCell>{boolBadge(source.enabled)}</TableCell>
                      <TableCell>
                        <div className="flex flex-wrap gap-2">
                          <Button variant="outline" size="sm" aria-label={`编辑数据源 ${source.name}`} onClick={() => openEditDataSourceDialog(source)}>编辑</Button>
                          <Button
                            variant="outline"
                            size="sm"
                            aria-label={`测试数据源 ${source.name}`}
                            onClick={() => actionMutation.mutate(() => configApi.testConfig({ config_type: "datasource", config_data: source as unknown as Record<string, unknown> }))}
                          >
                            测试
                          </Button>
                          <Button
                            variant="outline"
                            size="sm"
                            aria-label={`管理分组 ${source.name}`}
                            onClick={() => {
                              setGroupingForm({
                                data_source_name: source.name,
                                market_category_id: source.market_categories?.[0] || marketCategories[0]?.id || "",
                                priority: source.priority
                              })
                              setGroupingDialogOpen(true)
                            }}
                          >
                            分组
                          </Button>
                          <Button variant="outline" size="sm" onClick={() => actionMutation.mutate(() => configApi.setDefaultDataSource(source.name))}>设为默认</Button>
                          <Button variant="outline" size="sm" onClick={() => actionMutation.mutate(() => configApi.updateDataSourceConfig(source.name, { ...source, enabled: !source.enabled }))}>
                            {source.enabled ? "停用" : "启用"}
                          </Button>
                          <Button
                            variant="destructive"
                            size="sm"
                            onClick={() => setConfirm({
                              title: "删除数据源",
                              description: `确定要删除数据源 ${source.display_name || source.name} 吗？`,
                              confirmText: "删除",
                              onConfirm: () => actionMutation.mutate(() => configApi.deleteDataSourceConfig(source.name))
                            })}
                          >
                            删除
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </GenericTable>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle>市场分类</CardTitle>
              <div className="flex gap-2">
                <Button variant="outline" size="sm" onClick={() => setGroupingDialogOpen(true)}>绑定数据源</Button>
                <Button variant="outline" size="sm" onClick={() => setMarketDialogOpen(true)}>新增分类</Button>
              </div>
            </CardHeader>
            <CardContent className="space-y-6">
              <GenericTable rows={marketCategories} emptyText="暂无市场分类">
                <TableHeader>
                  <TableRow>
                    <TableHead>名称</TableHead>
                    <TableHead>排序</TableHead>
                    <TableHead>状态</TableHead>
                    <TableHead>操作</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {marketCategories.map((category, index) => (
                    <TableRow key={`${category.id}-${category.name}-${index}`}>
                      <TableCell>
                        <div className="font-medium">{category.display_name}</div>
                        <div className="text-xs text-muted-foreground">{category.name} / {category.description || "暂无描述"}</div>
                      </TableCell>
                      <TableCell>{category.sort_order}</TableCell>
                      <TableCell>{boolBadge(category.enabled)}</TableCell>
                      <TableCell>
                        <Button
                          variant="destructive"
                          size="sm"
                          onClick={() => setConfirm({
                            title: "删除市场分类",
                            description: `确定要删除市场分类 ${category.display_name} 吗？`,
                            confirmText: "删除",
                            onConfirm: () => actionMutation.mutate(() => configApi.deleteMarketCategory(category.id))
                          })}
                        >
                          删除
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </GenericTable>
              <div>
                <div className="mb-3 text-sm font-medium">数据源分组与排序</div>
                <GenericTable rows={groupings} emptyText="暂无数据源分组">
                  <TableHeader>
                    <TableRow>
                      <TableHead>市场分类</TableHead>
                      <TableHead>数据源</TableHead>
                      <TableHead>优先级</TableHead>
                      <TableHead>状态</TableHead>
                      <TableHead>排序</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {groupings.map((grouping, index) => (
                      <TableRow key={`${grouping.market_category_id}-${grouping.data_source_name}-${index}`}>
                        <TableCell>{marketCategories.find((item) => item.id === grouping.market_category_id)?.display_name || grouping.market_category_id}</TableCell>
                        <TableCell>{grouping.data_source_name}</TableCell>
                        <TableCell>{grouping.priority}</TableCell>
                        <TableCell>{boolBadge(grouping.enabled)}</TableCell>
                        <TableCell>
                          <div className="flex gap-2">
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => actionMutation.mutate(() => configApi.updateDataSourceGrouping(
                                grouping.data_source_name,
                                grouping.market_category_id,
                                { priority: Math.max(0, grouping.priority - 1) }
                              ))}
                            >
                              上移
                            </Button>
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => actionMutation.mutate(() => configApi.updateDataSourceGrouping(
                                grouping.data_source_name,
                                grouping.market_category_id,
                                { priority: grouping.priority + 1 }
                              ))}
                            >
                              下移
                            </Button>
                            <Button
                              variant="destructive"
                              size="sm"
                              onClick={() => setConfirm({
                                title: "移除数据源分组",
                                description: `确定要将 ${grouping.data_source_name} 从该市场分类移除吗？`,
                                confirmText: "移除",
                                onConfirm: () => actionMutation.mutate(() => configApi.removeDataSourceFromCategory(grouping.data_source_name, grouping.market_category_id))
                              })}
                            >
                              移除
                            </Button>
                          </div>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </GenericTable>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="database" className="mt-0">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle>数据库配置</CardTitle>
              <Button variant="outline" size="sm" onClick={openAddDatabaseDialog}>新增数据库</Button>
            </CardHeader>
            <CardContent>
              <GenericTable<DatabaseConfig> rows={databases} emptyText="暂无数据库配置">
                <TableHeader>
                  <TableRow>
                    <TableHead>名称</TableHead>
                    <TableHead>连接</TableHead>
                    <TableHead>连接池</TableHead>
                    <TableHead>状态</TableHead>
                    <TableHead>操作</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {databases.map((database) => (
                    <TableRow key={database.name}>
                      <TableCell>{database.name}</TableCell>
                      <TableCell>{database.type}://{database.host}:{database.port}/{database.database || "-"}</TableCell>
                      <TableCell>{database.pool_size} + {database.max_overflow}</TableCell>
                      <TableCell>{boolBadge(database.enabled)}</TableCell>
                      <TableCell>
                        <div className="flex flex-wrap gap-2">
                          <Button variant="outline" size="sm" aria-label={`编辑数据库 ${database.name}`} onClick={() => openEditDatabaseDialog(database)}>编辑</Button>
                          <Button variant="outline" size="sm" onClick={() => actionMutation.mutate(() => configApi.testDatabaseConfig(database.name))}>测试连接</Button>
                          <Button
                            variant="destructive"
                            size="sm"
                            onClick={() => setConfirm({
                              title: "删除数据库配置",
                              description: `确定要删除数据库配置 ${database.name} 吗？`,
                              confirmText: "删除",
                              onConfirm: () => actionMutation.mutate(() => configApi.deleteDatabaseConfig(database.name))
                            })}
                          >
                            删除
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </GenericTable>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="system" className="mt-0">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle>系统设置</CardTitle>
              <LoadingButton
                variant="outline"
                size="sm"
                loading={actionMutation.isPending}
                onClick={() => actionMutation.mutate(() => configApi.updateSystemSettings(settingsValues))}
              >
                保存系统设置
              </LoadingButton>
            </CardHeader>
            <CardContent className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
              {Object.entries(settingsValues).map(([key, value]) => {
                const meta = settingsMetaMap.get(key)
                const disabled = Boolean(meta && (!meta.editable || meta.sensitive || meta.source === "environment"))
                const label = ({
                  default_data_source: "数据供应商",
                  quick_analysis_model: "快速分析模型",
                  deep_analysis_model: "深度决策模型",
                  enable_cost_tracking: "启用成本跟踪",
                  cost_alert_threshold: "成本警告阈值",
                  currency_preference: "货币偏好",
                  timezone: "系统时区",
                  analysis_timeout: "分析超时时间",
                  enable_cache: "启用缓存",
                  cache_ttl: "缓存TTL",
                  log_level: "日志级别"
                } as Record<string, string>)[key] || key

                return (
                  <div key={key} className="grid gap-2 rounded-md border p-3">
                    <div className="flex items-center justify-between gap-2">
                      <Label htmlFor={`setting-${key}`}>{label}</Label>
                      {disabled ? <Badge variant="secondary">锁定</Badge> : null}
                    </div>
                    {typeof value === "boolean" ? (
                      <label className="flex items-center gap-2 text-sm">
                        <input id={`setting-${key}`} type="checkbox" checked={value} disabled={disabled} onChange={(event) => updateSettingDraft(key, event.target.checked)} />
                        {value ? "启用" : "关闭"}
                      </label>
                    ) : typeof value === "number" ? (
                      <Input id={`setting-${key}`} type="number" value={value} disabled={disabled} onChange={(event) => updateSettingDraft(key, Number(event.target.value) || 0)} />
                    ) : (
                      <Input id={`setting-${key}`} value={String(value ?? "")} disabled={disabled} onChange={(event) => updateSettingDraft(key, event.target.value)} />
                    )}
                    {meta ? <div className="text-xs text-muted-foreground">来源：{meta.source}</div> : null}
                  </div>
                )
              })}
              {!Object.keys(settingsValues).length ? <EmptyState title="暂无系统设置" className="md:col-span-2 xl:col-span-3" /> : null}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="api-keys" className="mt-0">
          <ApiKeyStatusPanel
            providers={providers}
            llmConfigs={llmConfigs}
            loading={providersQuery.isFetching}
            onRefresh={refreshConfig}
            onConfigure={openEditProviderDialog}
            onMigrate={() => actionMutation.mutate(() => configApi.migrateEnvToProviders())}
          />
        </TabsContent>

        <TabsContent value="import-export" className="mt-0">
          <div className="grid gap-4 lg:grid-cols-3">
            <Card>
              <CardHeader><CardTitle>配置导出</CardTitle></CardHeader>
              <CardContent className="space-y-3">
                <p className="text-sm text-muted-foreground">导出当前配置快照，用于备份或迁移。</p>
                <Button
                  variant="outline"
                  onClick={async () => {
                    try {
                      const result = await configApi.exportConfig()
                      const blob = new Blob([JSON.stringify(result.data, null, 2)], { type: "application/json" })
                      downloadBlob(blob, `trading-agents-config-${new Date().toISOString().slice(0, 10)}.json`)
                    } catch (error) {
                      toast.error(error instanceof Error ? error.message : "导出配置失败")
                    }
                  }}
                >
                  <Download className="mr-2 size-4" />导出配置
                </Button>
              </CardContent>
            </Card>
            <Card>
              <CardHeader><CardTitle>配置导入</CardTitle></CardHeader>
              <CardContent className="space-y-3">
                <Input aria-label="导入配置文件" type="file" accept=".json,application/json" onChange={(event) => setConfigImportFile(event.target.files?.[0] || null)} />
                <LoadingButton
                  loading={actionMutation.isPending}
                  disabled={!configImportFile}
                  onClick={() => {
                    if (!configImportFile) return
                    actionMutation.mutate(async () => {
                      const parsed = await parseImportFile(configImportFile)
                      await configApi.importConfig(parsed)
                      setConfigImportFile(null)
                    })
                  }}
                >
                  导入配置
                </LoadingButton>
              </CardContent>
            </Card>
            <Card>
              <CardHeader><CardTitle>配置迁移</CardTitle></CardHeader>
              <CardContent className="space-y-3">
                <p className="text-sm text-muted-foreground">迁移旧版配置结构到当前配置存储。</p>
                <LoadingButton loading={actionMutation.isPending} variant="outline" onClick={() => actionMutation.mutate(() => configApi.migrateLegacyConfig())}>迁移旧配置</LoadingButton>
              </CardContent>
            </Card>
          </div>
        </TabsContent>
      </Tabs>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{editingProvider ? "编辑厂家" : "新增厂家"}</DialogTitle>
            <DialogDescription>{editingProvider ? "更新大模型服务厂家信息。" : "添加新的大模型服务厂家配置。"}</DialogDescription>
          </DialogHeader>
          <form className="space-y-4" onSubmit={form.handleSubmit((values) => saveProviderMutation.mutate(values))}>
            <div className="grid gap-2">
              <Label htmlFor="provider-id">厂家 ID</Label>
              <Input id="provider-id" aria-label="厂家 ID" placeholder="dashscope" disabled={Boolean(editingProvider)} {...form.register("id")} />
              {form.formState.errors.id ? <p className="text-xs text-destructive">{form.formState.errors.id.message}</p> : null}
            </div>
            <div className="grid gap-2">
              <Label htmlFor="provider-name">厂家名称</Label>
              <Input id="provider-name" aria-label="厂家名称" placeholder="dashscope" {...form.register("name")} />
              {form.formState.errors.name ? <p className="text-xs text-destructive">{form.formState.errors.name.message}</p> : null}
            </div>
            <div className="grid gap-2">
              <Label htmlFor="provider-display-name">显示名称</Label>
              <Input id="provider-display-name" aria-label="显示名称" placeholder="通义千问" {...form.register("display_name")} />
              {form.formState.errors.display_name ? <p className="text-xs text-destructive">{form.formState.errors.display_name.message}</p> : null}
            </div>
            <div className="grid gap-2">
              <Label htmlFor="provider-api-key">API 密钥</Label>
              <Input id="provider-api-key" type="password" aria-label="API 密钥" placeholder={editingProvider ? "留空则保持原密钥" : undefined} {...form.register("api_key")} />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="provider-base-url">默认 Base URL</Label>
              <Input id="provider-base-url" aria-label="默认 Base URL" {...form.register("default_base_url")} />
            </div>
            <LoadingButton type="submit" loading={saveProviderMutation.isPending}>保存</LoadingButton>
          </form>
        </DialogContent>
      </Dialog>

      <Dialog open={modelDialogOpen} onOpenChange={setModelDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>新增模型目录</DialogTitle>
            <DialogDescription>为厂家维护可选模型目录。</DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="grid gap-2">
              <Label htmlFor="catalog-provider">厂家 ID</Label>
              <Input id="catalog-provider" value={modelForm.provider} onChange={(event) => setModelForm((value) => ({ ...value, provider: event.target.value }))} />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="catalog-provider-name">厂家名称</Label>
              <Input id="catalog-provider-name" value={modelForm.provider_name} onChange={(event) => setModelForm((value) => ({ ...value, provider_name: event.target.value }))} />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="catalog-model">模型名称</Label>
              <Input id="catalog-model" value={modelForm.model_name} onChange={(event) => setModelForm((value) => ({ ...value, model_name: event.target.value }))} />
            </div>
            <LoadingButton
              loading={actionMutation.isPending}
              onClick={() => {
                if (!modelForm.provider || !modelForm.provider_name || !modelForm.model_name) {
                  toast.error("请填写完整模型目录信息")
                  return
                }
                actionMutation.mutate(async () => {
                  await configApi.saveModelCatalog({
                    provider: modelForm.provider,
                    provider_name: modelForm.provider_name,
                    models: [{ name: modelForm.model_name, display_name: modelForm.model_name }]
                  })
                  setModelDialogOpen(false)
                  setModelForm({ provider: "", provider_name: "", model_name: "" })
                })
              }}
            >
              保存
            </LoadingButton>
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={dataSourceDialogOpen} onOpenChange={setDataSourceDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{editingDataSourceName ? "编辑数据源" : "新增数据源"}</DialogTitle>
            <DialogDescription>{editingDataSourceName ? "更新股票数据源配置。" : "创建股票数据源配置。"}</DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="grid gap-2">
              <Label htmlFor="datasource-name">数据源 ID</Label>
              <Input id="datasource-name" value={dataSourceForm.name} onChange={(event) => setDataSourceForm((value) => ({ ...value, name: event.target.value }))} />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="datasource-display-name">显示名称</Label>
              <Input id="datasource-display-name" value={dataSourceForm.display_name} onChange={(event) => setDataSourceForm((value) => ({ ...value, display_name: event.target.value }))} />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="datasource-priority">优先级</Label>
              <Input id="datasource-priority" type="number" value={dataSourceForm.priority} onChange={(event) => setDataSourceForm((value) => ({ ...value, priority: Number(event.target.value) || 1 }))} />
            </div>
            <LoadingButton
              loading={actionMutation.isPending}
              onClick={() => {
                if (!dataSourceForm.name) {
                  toast.error("请填写数据源 ID")
                  return
                }
                actionMutation.mutate(async () => {
                  const payload = {
                    name: dataSourceForm.name,
                    type: dataSourceForm.type,
                    display_name: dataSourceForm.display_name || dataSourceForm.name,
                    priority: dataSourceForm.priority,
                    timeout: 30,
                    rate_limit: 100,
                    enabled: true,
                    config_params: {}
                  }
                  if (editingDataSourceName) {
                    await configApi.updateDataSourceConfig(editingDataSourceName, payload)
                  } else {
                    await configApi.addDataSourceConfig(payload)
                  }
                  setDataSourceDialogOpen(false)
                  setEditingDataSourceName(null)
                  setDataSourceForm({ name: "", type: "stock", display_name: "", priority: 1 })
                })
              }}
            >
              保存
            </LoadingButton>
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={marketDialogOpen} onOpenChange={setMarketDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>新增市场分类</DialogTitle>
            <DialogDescription>创建市场分类，用于数据源分组和优先级排序。</DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <Input placeholder="分类 ID，例如 cn" value={marketForm.id} onChange={(event) => setMarketForm((value) => ({ ...value, id: event.target.value }))} />
            <Input placeholder="分类名称，例如 cn" value={marketForm.name} onChange={(event) => setMarketForm((value) => ({ ...value, name: event.target.value }))} />
            <Input placeholder="显示名称，例如 A股" value={marketForm.display_name} onChange={(event) => setMarketForm((value) => ({ ...value, display_name: event.target.value }))} />
            <LoadingButton
              loading={actionMutation.isPending}
              onClick={() => {
                if (!marketForm.id || !marketForm.name || !marketForm.display_name) {
                  toast.error("请填写完整市场分类信息")
                  return
                }
                actionMutation.mutate(async () => {
                  await configApi.addMarketCategory({ ...marketForm, enabled: true })
                  setMarketDialogOpen(false)
                  setMarketForm({ id: "", name: "", display_name: "", sort_order: 1 })
                })
              }}
            >
              保存
            </LoadingButton>
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={groupingDialogOpen} onOpenChange={setGroupingDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>绑定数据源</DialogTitle>
            <DialogDescription>将数据源加入市场分类，并设置分类内优先级。</DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <Select value={groupingForm.data_source_name || undefined} onValueChange={(value) => setGroupingForm((formValue) => ({ ...formValue, data_source_name: value }))}>
              <SelectTrigger><SelectValue placeholder="选择数据源" /></SelectTrigger>
              <SelectContent>
                {dataSources.map((source, index) => <SelectItem key={`${source.name}-${index}`} value={source.name}>{source.display_name || source.name}</SelectItem>)}
              </SelectContent>
            </Select>
            <Select value={groupingForm.market_category_id || undefined} onValueChange={(value) => setGroupingForm((formValue) => ({ ...formValue, market_category_id: value }))}>
              <SelectTrigger><SelectValue placeholder="选择市场分类" /></SelectTrigger>
              <SelectContent>
                {marketCategories.map((category, index) => <SelectItem key={`${category.id}-${index}`} value={category.id}>{category.display_name}</SelectItem>)}
              </SelectContent>
            </Select>
            <Input type="number" min={0} value={groupingForm.priority} onChange={(event) => setGroupingForm((value) => ({ ...value, priority: Number(event.target.value) || 0 }))} />
            <LoadingButton
              loading={actionMutation.isPending}
              onClick={() => {
                if (!groupingForm.data_source_name || !groupingForm.market_category_id) {
                  toast.error("请选择数据源和市场分类")
                  return
                }
                actionMutation.mutate(async () => {
                  await configApi.addDataSourceToCategory(groupingForm.data_source_name, groupingForm.market_category_id, groupingForm.priority)
                  setGroupingDialogOpen(false)
                  setGroupingForm({ data_source_name: "", market_category_id: "", priority: 1 })
                })
              }}
            >
              保存
            </LoadingButton>
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={databaseDialogOpen} onOpenChange={setDatabaseDialogOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>{editingDatabaseName ? "编辑数据库配置" : "新增数据库配置"}</DialogTitle>
            <DialogDescription>维护数据库连接、连接池和启用状态。</DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 md:grid-cols-2">
            <div className="grid gap-2">
              <Label htmlFor="database-name">配置名称</Label>
              <Input id="database-name" value={databaseForm.name} disabled={Boolean(editingDatabaseName)} onChange={(event) => setDatabaseForm((value) => ({ ...value, name: event.target.value }))} />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="database-type">数据库类型</Label>
              <Select value={databaseForm.type} onValueChange={(value) => setDatabaseForm((formValue) => ({ ...formValue, type: value }))}>
                <SelectTrigger id="database-type"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="postgresql">PostgreSQL</SelectItem>
                  <SelectItem value="postgres">Postgres</SelectItem>
                  <SelectItem value="redis">Redis</SelectItem>
                  <SelectItem value="mysql">MySQL</SelectItem>
                  <SelectItem value="sqlite">SQLite</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="database-host">主机地址</Label>
              <Input id="database-host" value={databaseForm.host} onChange={(event) => setDatabaseForm((value) => ({ ...value, host: event.target.value }))} />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="database-port">端口号</Label>
              <Input id="database-port" type="number" value={databaseForm.port} onChange={(event) => setDatabaseForm((value) => ({ ...value, port: Number(event.target.value) || 0 }))} />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="database-username">用户名</Label>
              <Input id="database-username" value={databaseForm.username} onChange={(event) => setDatabaseForm((value) => ({ ...value, username: event.target.value }))} />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="database-password">密码</Label>
              <Input id="database-password" type="password" value={databaseForm.password} placeholder={editingDatabaseName ? "留空则保持原密码" : undefined} onChange={(event) => setDatabaseForm((value) => ({ ...value, password: event.target.value }))} />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="database-database">数据库名</Label>
              <Input id="database-database" value={databaseForm.database} onChange={(event) => setDatabaseForm((value) => ({ ...value, database: event.target.value }))} />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="database-pool-size">连接池大小</Label>
              <Input id="database-pool-size" type="number" value={databaseForm.pool_size} onChange={(event) => setDatabaseForm((value) => ({ ...value, pool_size: Number(event.target.value) || 0 }))} />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="database-max-overflow">最大溢出连接</Label>
              <Input id="database-max-overflow" type="number" value={databaseForm.max_overflow} onChange={(event) => setDatabaseForm((value) => ({ ...value, max_overflow: Number(event.target.value) || 0 }))} />
            </div>
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={databaseForm.enabled} onChange={(event) => setDatabaseForm((value) => ({ ...value, enabled: event.target.checked }))} />
              启用状态
            </label>
            <div className="grid gap-2 md:col-span-2">
              <Label htmlFor="database-description">描述</Label>
              <Input id="database-description" value={databaseForm.description} onChange={(event) => setDatabaseForm((value) => ({ ...value, description: event.target.value }))} />
            </div>
          </div>
          <LoadingButton
            loading={actionMutation.isPending}
            onClick={() => {
              if (!databaseForm.name || !databaseForm.type || !databaseForm.host || !databaseForm.port) {
                toast.error("请填写完整数据库配置")
                return
              }
              actionMutation.mutate(async () => {
                const payload: Partial<DatabaseConfig> = {
                  name: databaseForm.name,
                  type: databaseForm.type,
                  host: databaseForm.host,
                  port: databaseForm.port,
                  username: databaseForm.username || undefined,
                  password: databaseForm.password || undefined,
                  database: databaseForm.database || undefined,
                  pool_size: databaseForm.pool_size,
                  max_overflow: databaseForm.max_overflow,
                  enabled: databaseForm.enabled,
                  description: databaseForm.description || undefined,
                  connection_params: {}
                }
                if (editingDatabaseName) {
                  await configApi.updateDatabaseConfig(editingDatabaseName, payload)
                } else {
                  await configApi.addDatabaseConfig(payload)
                }
                setDatabaseDialogOpen(false)
                setEditingDatabaseName(null)
              })
            }}
          >
            保存
          </LoadingButton>
        </DialogContent>
      </Dialog>

      <ConfirmDialog
        open={Boolean(confirm)}
        title={confirm?.title || ""}
        description={confirm?.description || ""}
        confirmText={confirm?.confirmText}
        destructive
        onOpenChange={(nextOpen) => {
          if (!nextOpen) setConfirm(null)
        }}
        onConfirm={() => {
          confirm?.onConfirm()
          setConfirm(null)
        }}
      />
    </div>
  )
}

export function DatabaseManagementPage() {
  const queryClient = useQueryClient()
  const [cleanupDays, setCleanupDays] = useState(30)
  const [logCleanupDays, setLogCleanupDays] = useState(90)
  const [exportMode, setExportMode] = useState("config_and_reports")
  const [importOverwrite, setImportOverwrite] = useState(false)
  const [importFile, setImportFile] = useState<File | null>(null)
  const [confirm, setConfirm] = useState<ConfirmState>(null)
  const statusQuery = useQuery({ queryKey: ["database", "status"], queryFn: () => databaseApi.getStatus(), retry: false })
  const statsQuery = useQuery({ queryKey: ["database", "stats"], queryFn: () => databaseApi.getStats(), retry: false })

  const actionMutation = useMutation({
    mutationFn: async (action: () => Promise<unknown>) => action(),
    onSuccess: () => {
      toast.success("操作已完成")
      void queryClient.invalidateQueries({ queryKey: ["database"] })
    },
    onError: (error) => toast.error(error.message)
  })
  const importMutation = useMutation({
    mutationFn: () => {
      if (!importFile) throw new Error("请选择要导入的 JSON 文件")
      return databaseApi.importData(importFile, { collection: "config_and_reports", format: "json", overwrite: importOverwrite })
    },
    onSuccess: () => {
      toast.success("数据导入完成")
      setImportFile(null)
      void queryClient.invalidateQueries({ queryKey: ["database"] })
    },
    onError: (error) => toast.error(error.message)
  })

  const status = statusQuery.data
  const stats = statsQuery.data
  const exportOptions = {
    config: { collections: ["llm_providers", "llm_configs", "data_sources", "system_settings", "market_categories", "datasource_groupings"], sanitize: true },
    config_and_reports: { collections: ["config_and_reports"], sanitize: true },
    all: { collections: undefined, sanitize: false }
  }[exportMode] || { collections: ["config_and_reports"], sanitize: true }

  const renderConnection = (name: string, item?: DatabaseStatus["postgres"] | DatabaseStatus["redis"]) => (
    <Card>
      <CardHeader><CardTitle>{name} 连接状态</CardTitle></CardHeader>
      <CardContent className="space-y-3">
        {boolBadge(Boolean(item?.connected), "已连接", "未连接")}
        <div className="text-sm text-muted-foreground">服务器：{item?.host || "-"}:{item?.port || "-"}</div>
        {"database" in (item || {}) ? <div className="text-sm text-muted-foreground">数据库：{String(item?.database ?? "-")}</div> : null}
        {"version" in (item || {}) ? <div className="text-sm text-muted-foreground">版本：{item?.version || "-"}</div> : null}
        {item?.error ? <div className="text-sm text-destructive">{item.error}</div> : null}
      </CardContent>
    </Card>
  )

  return (
    <div>
      <PageHeader
        title="数据库管理"
        description="PostgreSQL + Redis 数据库管理和监控"
        actions={<LoadingButton variant="outline" loading={statusQuery.isFetching} onClick={() => void statusQuery.refetch()}>刷新状态</LoadingButton>}
      />
      <div className="grid gap-4 md:grid-cols-2">
        {renderConnection("PostgreSQL", status?.postgres)}
        {renderConnection("Redis", status?.redis)}
      </div>
      <div className="mt-4 grid gap-4 md:grid-cols-3">
        <StatCard label="PostgreSQL 集合数" value={stats?.total_collections ?? 0} />
        <StatCard label="文档数" value={stats?.total_documents ?? 0} />
        <StatCard label="数据库大小" value={formatBytes(stats?.total_size ?? 0)} />
      </div>
      <Card className="mt-6">
        <CardHeader><CardTitle>数据管理操作</CardTitle></CardHeader>
        <CardContent className="grid gap-6 lg:grid-cols-2">
          <div className="space-y-3 rounded-md border p-4">
            <h3 className="font-medium">数据导出</h3>
            <p className="text-sm text-muted-foreground">导出数据库数据到文件</p>
            <Label>导出格式</Label>
            <Select value="json">
              <SelectTrigger aria-label="导出格式"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="json">JSON</SelectItem>
                <SelectItem value="csv">CSV</SelectItem>
                <SelectItem value="xlsx">Excel</SelectItem>
              </SelectContent>
            </Select>
            <Label>数据集合</Label>
            <Select value={exportMode} onValueChange={setExportMode}>
              <SelectTrigger aria-label="数据集合"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="config_and_reports">配置和报告（用于迁移）</SelectItem>
                <SelectItem value="config">配置数据（用于演示系统，已脱敏）</SelectItem>
                <SelectItem value="analysis_reports">分析报告</SelectItem>
                <SelectItem value="user_configs">用户配置</SelectItem>
                <SelectItem value="operation_logs">操作日志</SelectItem>
                <SelectItem value="all">全部数据</SelectItem>
              </SelectContent>
            </Select>
            <Button
              variant="outline"
              onClick={async () => {
                try {
                  const blob = await databaseApi.exportData({ ...exportOptions, format: "json" })
                  downloadBlob(blob, `trading-agents-${exportMode}-${new Date().toISOString().slice(0, 10)}.json`)
                } catch (error) {
                  toast.error(error instanceof Error ? error.message : "导出失败")
                }
              }}
            >
              <Download className="mr-2 size-4" />导出数据
            </Button>
          </div>
          <div className="space-y-3 rounded-md border p-4">
            <h3 className="font-medium">数据导入</h3>
            <p className="text-sm text-muted-foreground">从导出文件导入数据</p>
            <Label>选择文件</Label>
            <Input aria-label="选择文件" type="file" accept=".json,application/json" onChange={(event) => setImportFile(event.target.files?.[0] || null)} />
            <Label>导入选项</Label>
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={importOverwrite} onChange={(event) => setImportOverwrite(event.target.checked)} />
              覆盖现有数据
            </label>
            <div className="text-xs text-muted-foreground">勾选后将删除现有数据再导入</div>
            <LoadingButton loading={importMutation.isPending} disabled={!importFile} onClick={() => importMutation.mutate()}>导入数据</LoadingButton>
          </div>
          <div className="space-y-3 rounded-md border p-4 lg:col-span-2">
            <h3 className="font-medium">数据备份与还原</h3>
            <div className="rounded-md border bg-muted/40 p-3 text-sm text-muted-foreground">
              <p className="font-medium text-foreground">请使用命令行工具进行备份和还原</p>
              <p className="mt-2">由于数据量较大，Web 界面备份体验较差，建议使用 PostgreSQL 原生工具。</p>
              <code className="mt-2 block rounded bg-background p-2">pg_dump postgresql://postgres:postgres@localhost:5432/trading_agents_cn --format=custom --file=./backup/trading_agents.dump</code>
              <code className="mt-2 block rounded bg-background p-2">pg_restore --dbname=postgresql://postgres:postgres@localhost:5432/trading_agents_cn ./backup/trading_agents.dump</code>
            </div>
          </div>
        </CardContent>
      </Card>
      <Card className="mt-6">
        <CardHeader><CardTitle>数据清理</CardTitle></CardHeader>
        <CardContent className="grid gap-4 md:grid-cols-3">
          <div className="rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900 md:col-span-3">危险操作：以下操作将永久删除数据，请谨慎操作</div>
          <LoadingButton loading={actionMutation.isPending} onClick={() => actionMutation.mutate(() => databaseApi.testConnections())}>测试连接</LoadingButton>
          <div className="flex gap-2">
            <Input aria-label="分析结果清理天数" type="number" min={1} max={365} value={cleanupDays} onChange={(event) => setCleanupDays(Number(event.target.value) || 30)} />
            <Button
              variant="destructive"
              onClick={() => setConfirm({
                title: "清理过期分析结果",
                description: `确定要删除 ${cleanupDays} 天前的分析结果吗？此操作不可恢复。`,
                confirmText: "清理",
                onConfirm: () => actionMutation.mutate(() => databaseApi.cleanupAnalysisResults(cleanupDays))
              })}
            >
              清理分析结果
            </Button>
          </div>
          <div className="flex gap-2">
            <Input aria-label="操作日志清理天数" type="number" min={1} max={365} value={logCleanupDays} onChange={(event) => setLogCleanupDays(Number(event.target.value) || 90)} />
            <Button
              variant="destructive"
              onClick={() => setConfirm({
                title: "清理操作日志",
                description: `确定要删除 ${logCleanupDays} 天前的操作日志吗？此操作不可恢复。`,
                confirmText: "清理",
                onConfirm: () => actionMutation.mutate(() => databaseApi.cleanupOperationLogs(logCleanupDays))
              })}
            >
              清理操作日志
            </Button>
          </div>
        </CardContent>
      </Card>
      <ConfirmDialog
        open={Boolean(confirm)}
        title={confirm?.title || ""}
        description={confirm?.description || ""}
        confirmText={confirm?.confirmText}
        destructive
        onOpenChange={(nextOpen) => {
          if (!nextOpen) setConfirm(null)
        }}
        onConfirm={() => {
          confirm?.onConfirm()
          setConfirm(null)
        }}
      />
    </div>
  )
}

export function OperationLogsPage() {
  const [keyword, setKeyword] = useState("")
  const [actionType, setActionType] = useState("all")
  const [success, setSuccess] = useState("all")
  const [startDate, setStartDate] = useState("")
  const [endDate, setEndDate] = useState("")
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState("50")
  const [selectedLog, setSelectedLog] = useState<OperationLog | null>(null)
  const [confirm, setConfirm] = useState<ConfirmState>(null)
  const queryClient = useQueryClient()

  const logsQuery = useQuery({
    queryKey: ["operation-logs", keyword, actionType, success, startDate, endDate, page, pageSize],
    queryFn: () => OperationLogsApi.getOperationLogs({
      page,
      page_size: Number(pageSize),
      keyword: keyword || undefined,
      start_date: startDate || undefined,
      end_date: endDate || undefined,
      action_type: actionType === "all" ? undefined : actionType,
      success: success === "all" ? undefined : success === "success"
    }),
    retry: false
  })
  const statsQuery = useQuery({ queryKey: ["operation-logs", "stats"], queryFn: () => OperationLogsApi.getOperationLogStats(30), retry: false })
  const clearMutation = useMutation({
    mutationFn: () => OperationLogsApi.clearOperationLogs({}),
    onSuccess: () => {
      toast.success("操作日志已清空")
      void queryClient.invalidateQueries({ queryKey: ["operation-logs"] })
    },
    onError: (error) => toast.error(error.message)
  })

  const logs = logsQuery.data?.logs || []
  const total = logsQuery.data?.total || 0
  const totalPages = logsQuery.data?.total_pages || Math.max(1, Math.ceil(total / Number(pageSize)))
  const stats = statsQuery.data

  return (
    <div>
      <PageHeader
        title="操作日志"
        description="系统操作日志查看、过滤和分析"
        actions={<Button variant="outline" onClick={() => void logsQuery.refetch()}>刷新</Button>}
      />
      <div className="grid gap-4 md:grid-cols-4">
        <StatCard label="总日志数" value={stats?.total_logs ?? 0} />
        <StatCard label="成功操作" value={stats?.success_logs ?? 0} />
        <StatCard label="失败操作" value={stats?.failed_logs ?? 0} />
        <StatCard label="成功率" value={`${stats?.success_rate ?? 0}%`} />
      </div>
      <Card className="mt-6">
        <CardHeader><CardTitle>筛选控制面板</CardTitle></CardHeader>
        <CardContent className="grid gap-3 md:grid-cols-4">
          <div className="space-y-2">
            <Label>时间范围</Label>
            <div className="grid gap-2 sm:grid-cols-2">
              <Input aria-label="开始时间" type="datetime-local" value={startDate} onChange={(event) => { setStartDate(event.target.value); setPage(1) }} />
              <Input aria-label="结束时间" type="datetime-local" value={endDate} onChange={(event) => { setEndDate(event.target.value); setPage(1) }} />
            </div>
          </div>
          <div className="space-y-2">
            <Label>操作类型</Label>
          <Select value={actionType} onValueChange={setActionType}>
            <SelectTrigger><SelectValue placeholder="全部类型" /></SelectTrigger>
            <SelectContent>
              <SelectItem value="all">全部类型</SelectItem>
              {Object.values(ActionTypes).map((type) => <SelectItem key={type} value={type}>{getActionTypeName(type)}</SelectItem>)}
            </SelectContent>
          </Select>
          </div>
          <div className="space-y-2">
            <Label>操作状态</Label>
          <Select value={success} onValueChange={setSuccess}>
            <SelectTrigger><SelectValue placeholder="全部状态" /></SelectTrigger>
            <SelectContent>
              <SelectItem value="all">全部状态</SelectItem>
              <SelectItem value="success">成功</SelectItem>
              <SelectItem value="failed">失败</SelectItem>
            </SelectContent>
          </Select>
          </div>
          <div className="space-y-2">
            <Label>关键词</Label>
            <Input placeholder="搜索操作内容" value={keyword} onChange={(event) => { setKeyword(event.target.value); setPage(1) }} />
          </div>
          <Select value={pageSize} onValueChange={(value) => { setPageSize(value); setPage(1) }}>
            <SelectTrigger aria-label="每页条数"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="20">20 条/页</SelectItem>
              <SelectItem value="50">50 条/页</SelectItem>
              <SelectItem value="100">100 条/页</SelectItem>
              <SelectItem value="200">200 条/页</SelectItem>
            </SelectContent>
          </Select>
          <Button onClick={() => void logsQuery.refetch()}>查询</Button>
          <Button
            variant="outline"
            onClick={() => {
              setKeyword("")
              setActionType("all")
              setSuccess("all")
              setStartDate("")
              setEndDate("")
              setPage(1)
            }}
          >
            重置
          </Button>
          <Button
            variant="outline"
            onClick={async () => {
              try {
                const blob = await OperationLogsApi.exportOperationLogsCSV({
                  start_date: startDate || undefined,
                  end_date: endDate || undefined,
                  action_type: actionType === "all" ? undefined : actionType
                })
                downloadBlob(blob, `operation-logs-${new Date().toISOString().slice(0, 10)}.csv`)
              } catch (error) {
                toast.error(error instanceof Error ? error.message : "导出操作日志失败")
              }
            }}
          >
            <Download className="mr-2 size-4" />导出
          </Button>
          <Button
            variant="destructive"
            onClick={() => setConfirm({
              title: "清空操作日志",
              description: "确定要清空匹配当前筛选条件的操作日志吗？此操作不可恢复。",
              confirmText: "清空",
              onConfirm: () => clearMutation.mutate()
            })}
          >
            清空日志
          </Button>
        </CardContent>
      </Card>
      <div className="mt-6 grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader><CardTitle>操作类型分布</CardTitle></CardHeader>
          <CardContent className="h-40 text-sm text-muted-foreground">按操作类型统计当前日志分布。</CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle>操作趋势</CardTitle></CardHeader>
          <CardContent className="h-40 text-sm text-muted-foreground">按时间维度展示操作变化趋势。</CardContent>
        </Card>
      </div>
      <Card className="mt-6">
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle>操作日志列表</CardTitle>
          <div className="flex gap-2">
            <Button size="sm" variant="outline" onClick={() => void logsQuery.refetch()}>刷新</Button>
            <Button size="sm" variant="destructive" onClick={() => setConfirm({
              title: "清空操作日志",
              description: "确定要清空匹配当前筛选条件的操作日志吗？此操作不可恢复。",
              confirmText: "清空",
              onConfirm: () => clearMutation.mutate()
            })}>清空日志</Button>
          </div>
        </CardHeader>
        <CardContent>
          <GenericTable<OperationLog> rows={logs} emptyText="暂无操作日志">
            <TableHeader>
              <TableRow>
                <TableHead>时间</TableHead>
                <TableHead>类型</TableHead>
                <TableHead>操作内容</TableHead>
                <TableHead>状态</TableHead>
                <TableHead>耗时</TableHead>
                <TableHead>IP</TableHead>
                <TableHead>操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {logs.map((log) => (
                <TableRow key={log.id}>
                  <TableCell>{formatDateTime(log.timestamp)}</TableCell>
                  <TableCell>{getActionTypeName(log.action_type)}</TableCell>
                  <TableCell>{log.action}</TableCell>
                  <TableCell>{boolBadge(log.success, "成功", "失败")}</TableCell>
                  <TableCell>{log.duration_ms ? `${log.duration_ms}ms` : "-"}</TableCell>
                  <TableCell>{log.ip_address || "-"}</TableCell>
                  <TableCell><Button size="sm" variant="outline" onClick={() => setSelectedLog(log)}>详情</Button></TableCell>
                </TableRow>
              ))}
            </TableBody>
          </GenericTable>
          <div className="mt-4 flex flex-wrap items-center justify-between gap-3 text-sm text-muted-foreground">
            <div>共 {total} 条，第 {page} / {totalPages} 页</div>
            <div className="flex gap-2">
              <Button size="sm" variant="outline" disabled={page <= 1} onClick={() => setPage((value) => Math.max(1, value - 1))}>上一页</Button>
              <Button size="sm" variant="outline" disabled={page >= totalPages} onClick={() => setPage((value) => value + 1)}>下一页</Button>
            </div>
          </div>
        </CardContent>
      </Card>
      <Dialog open={Boolean(selectedLog)} onOpenChange={(nextOpen) => !nextOpen && setSelectedLog(null)}>
        <DialogContent className="max-w-3xl">
          <DialogHeader>
            <DialogTitle>操作日志详情</DialogTitle>
            <DialogDescription>{selectedLog ? `${formatDateTime(selectedLog.timestamp)} / ${getActionTypeName(selectedLog.action_type)}` : ""}</DialogDescription>
          </DialogHeader>
          <div className="grid gap-3 text-sm md:grid-cols-2">
            <div>用户：{selectedLog?.username || selectedLog?.user_id || "-"}</div>
            <div>状态：{selectedLog ? (selectedLog.success ? "成功" : "失败") : "-"}</div>
            <div>耗时：{selectedLog?.duration_ms ? `${selectedLog.duration_ms}ms` : "-"}</div>
            <div>IP：{selectedLog?.ip_address || "-"}</div>
            <div className="md:col-span-2">会话：{selectedLog?.session_id || "-"}</div>
            <div className="md:col-span-2">操作：{selectedLog?.action || "-"}</div>
          </div>
          {selectedLog?.error_message ? <pre className="max-h-40 overflow-auto rounded-md bg-destructive/10 p-3 text-sm text-destructive">{selectedLog.error_message}</pre> : null}
          {selectedLog?.details ? <pre className="max-h-64 overflow-auto rounded-md bg-muted p-3 text-xs">{JSON.stringify(selectedLog.details, null, 2)}</pre> : null}
        </DialogContent>
      </Dialog>
      <ConfirmDialog
        open={Boolean(confirm)}
        title={confirm?.title || ""}
        description={confirm?.description || ""}
        confirmText={confirm?.confirmText}
        destructive
        onOpenChange={(nextOpen) => {
          if (!nextOpen) setConfirm(null)
        }}
        onConfirm={() => {
          confirm?.onConfirm()
          setConfirm(null)
        }}
      />
    </div>
  )
}

export function SystemLogsPage() {
  const [keyword, setKeyword] = useState("")
  const [selectedFile, setSelectedFile] = useState<LogFileInfo | null>(null)
  const [viewLevel, setViewLevel] = useState("all")
  const [viewKeyword, setViewKeyword] = useState("")
  const [viewLines, setViewLines] = useState(1000)
  const [exportOpen, setExportOpen] = useState(false)
  const [exportLevel, setExportLevel] = useState("all")
  const [exportFormat, setExportFormat] = useState<"txt" | "zip">("zip")
  const [exportNames, setExportNames] = useState("")
  const [confirm, setConfirm] = useState<ConfirmState>(null)
  const queryClient = useQueryClient()

  const filesQuery = useQuery({ queryKey: ["system-logs", "files"], queryFn: () => LogsApi.listLogFiles(), retry: false })
  const statsQuery = useQuery({ queryKey: ["system-logs", "stats"], queryFn: () => LogsApi.getStatistics(7), retry: false })
  const contentQuery = useQuery({
    queryKey: ["system-logs", "content", selectedFile?.name, viewLevel, viewKeyword, viewLines],
    queryFn: () => LogsApi.readLogFile({
      filename: selectedFile?.name || "",
      lines: viewLines,
      level: viewLevel === "all" ? undefined : viewLevel as "ERROR" | "WARNING" | "INFO" | "DEBUG",
      keyword: viewKeyword || undefined
    }),
    enabled: Boolean(selectedFile),
    retry: false
  })
  const deleteMutation = useMutation({
    mutationFn: (filename: string) => LogsApi.deleteLogFile(filename),
    onSuccess: () => {
      toast.success("日志文件已删除")
      void queryClient.invalidateQueries({ queryKey: ["system-logs"] })
    },
    onError: (error) => toast.error(error.message)
  })

  const files = (filesQuery.data || []).filter((file) => file.name.toLowerCase().includes(keyword.toLowerCase()))
  const stats = statsQuery.data

  return (
    <div>
      <PageHeader
        title="日志管理"
        description="系统日志文件查看、过滤、导出和删除"
        actions={
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" onClick={() => void filesQuery.refetch()}>刷新</Button>
            <Button variant="outline" onClick={() => setExportOpen(true)}><Download className="mr-2 size-4" />导出日志</Button>
          </div>
        }
      />
      <div className="grid gap-4 md:grid-cols-3">
        <StatCard label="日志文件数" value={stats?.total_files ?? 0} />
        <StatCard label="总大小 (MB)" value={stats?.total_size_mb?.toFixed?.(2) ?? 0} />
        <StatCard label="错误日志文件" value={stats?.error_files ?? 0} />
      </div>
      <div className="mt-3">
        <Button variant="outline" onClick={() => void statsQuery.refetch()}>刷新统计</Button>
      </div>
      <Card className="mt-6">
        <CardHeader><CardTitle>日志文件列表</CardTitle></CardHeader>
        <CardContent className="space-y-4">
          <Label htmlFor="system-log-search">搜索文件名</Label>
          <Input id="system-log-search" placeholder="搜索文件名" value={keyword} onChange={(event) => setKeyword(event.target.value)} />
          <GenericTable<LogFileInfo> rows={files} emptyText="暂无日志文件">
            <TableHeader>
              <TableRow>
                <TableHead>文件名</TableHead>
                <TableHead>类型</TableHead>
                <TableHead>大小 (MB)</TableHead>
                <TableHead>修改时间</TableHead>
                <TableHead>操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {files.map((file) => (
                <TableRow key={file.name}>
                  <TableCell>{file.name}</TableCell>
                  <TableCell>{file.type}</TableCell>
                  <TableCell>{file.size_mb.toFixed(2)} MB</TableCell>
                  <TableCell>{formatDateTime(file.modified_at)}</TableCell>
                  <TableCell>
                    <div className="flex flex-wrap gap-2">
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => {
                          setSelectedFile(file)
                          setViewKeyword("")
                          setViewLevel("all")
                          setViewLines(1000)
                        }}
                      >
                        查看
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={async () => {
                          const blob = await LogsApi.exportLogs({ filenames: [file.name], format: "txt" })
                          downloadBlob(blob, `${file.name}.txt`)
                        }}
                      >
                        下载
                      </Button>
                      <Button
                        size="sm"
                        variant="destructive"
                        onClick={() => setConfirm({
                          title: "删除日志文件",
                          description: `确定要删除日志文件 ${file.name} 吗？`,
                          confirmText: "删除",
                          onConfirm: () => deleteMutation.mutate(file.name)
                        })}
                      >
                        删除
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </GenericTable>
        </CardContent>
      </Card>
      <Dialog open={Boolean(selectedFile)} onOpenChange={(nextOpen) => !nextOpen && setSelectedFile(null)}>
        <DialogContent className="max-w-4xl">
          <DialogHeader>
            <DialogTitle>{selectedFile?.name || "日志内容"}</DialogTitle>
            <DialogDescription>按级别、关键词和行数读取日志内容。</DialogDescription>
          </DialogHeader>
          <div className="grid gap-3 md:grid-cols-4">
            <Select value={viewLevel} onValueChange={setViewLevel}>
              <SelectTrigger aria-label="日志级别"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="all">全部级别</SelectItem>
                <SelectItem value="ERROR">ERROR</SelectItem>
                <SelectItem value="WARNING">WARNING</SelectItem>
                <SelectItem value="INFO">INFO</SelectItem>
                <SelectItem value="DEBUG">DEBUG</SelectItem>
              </SelectContent>
            </Select>
            <Input placeholder="搜索关键词" value={viewKeyword} onChange={(event) => setViewKeyword(event.target.value)} />
            <Input aria-label="读取行数" type="number" min={100} max={10000} step={100} value={viewLines} onChange={(event) => setViewLines(Number(event.target.value) || 1000)} />
            <Button variant="outline" onClick={() => void contentQuery.refetch()}>筛选</Button>
          </div>
          {contentQuery.data?.stats ? (
            <div className="grid gap-2 text-sm text-muted-foreground md:grid-cols-5">
              <div>总行数：{contentQuery.data.stats.total_lines}</div>
              <div>过滤后：{contentQuery.data.stats.filtered_lines}</div>
              <div>ERROR：{contentQuery.data.stats.error_count}</div>
              <div>WARNING：{contentQuery.data.stats.warning_count}</div>
              <div>INFO：{contentQuery.data.stats.info_count}</div>
            </div>
          ) : null}
          <pre className="max-h-[60vh] overflow-auto rounded-md bg-muted p-4 text-xs">
            {(contentQuery.data?.lines || []).join("\n") || "暂无日志内容"}
          </pre>
        </DialogContent>
      </Dialog>
      <Dialog open={exportOpen} onOpenChange={setExportOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>导出日志</DialogTitle>
            <DialogDescription>可按文件名和日志级别导出，文件名留空表示导出全部日志。</DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="grid gap-2">
              <Label htmlFor="export-log-names">日志文件名</Label>
              <Input id="export-log-names" placeholder="多个文件用逗号分隔" value={exportNames} onChange={(event) => setExportNames(event.target.value)} />
            </div>
            <div className="grid gap-2">
              <Label>日志级别</Label>
              <Select value={exportLevel} onValueChange={setExportLevel}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">全部级别</SelectItem>
                  <SelectItem value="ERROR">ERROR</SelectItem>
                  <SelectItem value="WARNING">WARNING</SelectItem>
                  <SelectItem value="INFO">INFO</SelectItem>
                  <SelectItem value="DEBUG">DEBUG</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="grid gap-2">
              <Label>导出格式</Label>
              <Select value={exportFormat} onValueChange={(value: "txt" | "zip") => setExportFormat(value)}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="zip">ZIP</SelectItem>
                  <SelectItem value="txt">TXT</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <Button
              onClick={async () => {
                try {
                  const filenames = exportNames.split(",").map((name) => name.trim()).filter(Boolean)
                  const blob = await LogsApi.exportLogs({
                    filenames: filenames.length ? filenames : undefined,
                    level: exportLevel === "all" ? undefined : exportLevel as "ERROR" | "WARNING" | "INFO" | "DEBUG",
                    format: exportFormat
                  })
                  downloadBlob(blob, `logs-export-${new Date().toISOString().slice(0, 10)}.${exportFormat}`)
                  setExportOpen(false)
                } catch (error) {
                  toast.error(error instanceof Error ? error.message : "导出日志失败")
                }
              }}
            >
              导出
            </Button>
          </div>
        </DialogContent>
      </Dialog>
      <ConfirmDialog
        open={Boolean(confirm)}
        title={confirm?.title || ""}
        description={confirm?.description || ""}
        confirmText={confirm?.confirmText}
        destructive
        onOpenChange={(nextOpen) => {
          if (!nextOpen) setConfirm(null)
        }}
        onConfirm={() => {
          confirm?.onConfirm()
          setConfirm(null)
        }}
      />
    </div>
  )
}

function getSyncStatusText(status?: string) {
  const textMap: Record<string, string> = {
    idle: "空闲",
    running: "运行中",
    success: "成功",
    success_with_errors: "部分成功",
    failed: "失败",
    never_run: "未运行"
  }

  return textMap[status || "never_run"] || "未知"
}

function syncStatusBadge(status?: string) {
  const label = getSyncStatusText(status)
  const classNameMap: Record<string, string> = {
    running: "border-amber-200 bg-amber-50 text-amber-900",
    success: "border-emerald-200 bg-emerald-50 text-emerald-900",
    success_with_errors: "border-amber-200 bg-amber-50 text-amber-900",
    failed: "border-destructive/30 bg-destructive/5 text-destructive",
    idle: "border-border bg-muted text-muted-foreground",
    never_run: "border-border bg-muted text-muted-foreground"
  }

  return <Badge variant="outline" className={classNameMap[status || "never_run"] || classNameMap.never_run}>{label}</Badge>
}

function getSyncButtonText(status: SyncStatus | undefined, syncing: boolean, progress: number) {
  if (syncing) return "启动中..."
  if (status?.status === "running") return progress > 0 ? `同步中 ${progress}%` : "同步中..."
  return "开始同步"
}

function formatSyncHistoryTime(time?: string) {
  if (!time) return ""
  const date = new Date(time)
  if (Number.isNaN(date.getTime())) return time

  const diff = Date.now() - date.getTime()
  if (diff >= 0 && diff < 24 * 60 * 60 * 1000) {
    return date.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit", second: "2-digit" })
  }

  return date.toLocaleString("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" })
}

function getSyncDuration(startTime?: string, endTime?: string) {
  if (!startTime || !endTime) return ""
  const start = new Date(startTime).getTime()
  const end = new Date(endTime).getTime()
  if (Number.isNaN(start) || Number.isNaN(end)) return ""

  const duration = Math.max(0, end - start)
  if (duration < 1000) return `${duration}ms`
  if (duration < 60000) return `${Math.round(duration / 1000)}s`

  const minutes = Math.floor(duration / 60000)
  const seconds = Math.round((duration % 60000) / 1000)
  return `${minutes}m ${seconds}s`
}

function getPreferredSourcesExample(recommendations?: {
  primary_source?: { name: string }
  fallback_sources?: Array<{ name: string }>
}) {
  const sources = [
    recommendations?.primary_source?.name,
    recommendations?.fallback_sources?.[0]?.name
  ].filter(Boolean)

  return sources.join(",") || "tushare,akshare"
}

export function SyncManagementPage() {
  const [force, setForce] = useState(false)
  const [preferredSources, setPreferredSources] = useState<string[]>([])
  const [historyPage, setHistoryPage] = useState(1)
  const [testResults, setTestResults] = useState<DataSourceTestResult[]>([])
  const [testDialogOpen, setTestDialogOpen] = useState(false)
  const [sourceTestResults, setSourceTestResults] = useState<Record<string, DataSourceTestResult>>({})
  const [confirm, setConfirm] = useState<ConfirmState>(null)
  const queryClient = useQueryClient()
  const statusQuery = useQuery({ queryKey: ["sync", "status"], queryFn: () => getSyncStatus().then(getResponseData), retry: false })
  const sourcesQuery = useQuery({ queryKey: ["sync", "sources"], queryFn: () => getDataSourcesStatus().then(getResponseData), retry: false })
  const recommendationsQuery = useQuery({ queryKey: ["sync", "recommendations"], queryFn: () => getSyncRecommendations().then(getResponseData), retry: false })
  const historyQuery = useQuery({ queryKey: ["sync", "history", historyPage], queryFn: () => getSyncHistory({ page: 1, page_size: historyPage * 10 }).then(getResponseData), retry: false })

  const syncMutation = useMutation({
    mutationFn: (params: { force?: boolean; preferred_sources?: string }) => runStockBasicsSync(params).then(getResponseData),
    onSuccess: (data) => {
      toast.success(data.status === "running" ? "同步任务已启动" : `同步状态：${getSyncStatusText(data.status)}`)
      void queryClient.invalidateQueries({ queryKey: ["sync"] })
    },
    onError: (error) => toast.error(error.message)
  })
  const testMutation = useMutation({
    mutationFn: (sourceName?: string) => testDataSources(sourceName).then(getResponseData),
    onSuccess: (data, sourceName) => {
      setTestResults(data.test_results)
      setSourceTestResults((value) => ({
        ...value,
        ...Object.fromEntries(data.test_results.map((item) => [item.name, item]))
      }))
      if (sourceName) {
        const result = data.test_results.find((item) => item.name === sourceName)
        if (result?.available) {
          toast.success(`${sourceName.toUpperCase()} 连接成功`)
        } else {
          toast.warning(`${sourceName.toUpperCase()} 连接失败：${result?.message || "未知错误"}`)
        }
        return
      }

      setTestDialogOpen(true)
      toast.success(`全面测试完成：${data.test_results.filter((item) => item.available).length}/${data.test_results.length} 数据源可用`)
    },
    onError: (error) => toast.error(error.message)
  })
  const maintenanceMutation = useMutation({
    mutationFn: async (action: () => Promise<unknown>) => action(),
    onSuccess: () => {
      toast.success("同步操作已完成")
      void queryClient.invalidateQueries({ queryKey: ["sync"] })
    },
    onError: (error) => toast.error(error.message)
  })

  const status = statusQuery.data
  const sources = [...(sourcesQuery.data || [])].sort((left, right) => right.priority - left.priority)
  const history = historyQuery.data?.records || []
  const recommendations = recommendationsQuery.data
  const processed = (status?.inserted || 0) + (status?.updated || 0)
  const progress = status?.total ? Math.min(100, Math.round((processed / status.total) * 100)) : 0
  const isRunning = status?.status === "running"
  const historyHasMore = Boolean(historyQuery.data?.has_more)
  const selectedPreferredSources = preferredSources.filter((sourceName) => sources.some((source) => source.name === sourceName))
  const startSync = (overrideForce = force) => {
    syncMutation.mutate({
      force: overrideForce,
      preferred_sources: selectedPreferredSources.length ? selectedPreferredSources.join(",") : undefined
    })
  }
  const refreshAll = () => {
    void statusQuery.refetch()
    void sourcesQuery.refetch()
    void recommendationsQuery.refetch()
    void historyQuery.refetch()
  }

  useEffect(() => {
    if (!isRunning) return

    const timer = window.setInterval(() => {
      void statusQuery.refetch()
      void historyQuery.refetch()
    }, 5000)

    return () => window.clearInterval(timer)
  }, [historyQuery, isRunning, statusQuery])

  return (
    <div>
      <PageHeader
        title="多数据源同步"
        description="管理和监控多个数据源的股票基础信息同步，支持自动fallback和优先级配置"
        actions={
          <div className="flex flex-wrap gap-2">
            <LoadingButton loading={testMutation.isPending} onClick={() => testMutation.mutate(undefined)}>
              <RefreshCw className="size-4" />
              全面测试
            </LoadingButton>
            <Button variant="outline" onClick={() => {
              refreshAll()
            }}>
              <RefreshCw className="size-4" />
              刷新
            </Button>
          </div>
        }
      />

      <div className="grid gap-6 lg:grid-cols-2">
        <div className="space-y-6">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between gap-3">
            <CardTitle>数据源状态</CardTitle>
            <Button size="sm" variant="outline" onClick={() => void sourcesQuery.refetch()}>
              <RefreshCw className="size-4" />
              刷新
            </Button>
          </CardHeader>
          <CardContent className="space-y-3">
            {sources.map((source) => (
              <div key={source.name} className={`rounded-md border p-4 ${source.available ? "border-emerald-200 bg-emerald-50/40" : "border-destructive/25 bg-destructive/5"}`}>
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge variant={source.available ? "default" : "destructive"}>{source.available ? "可用" : "不可用"}</Badge>
                    <div className="font-semibold uppercase">{source.name}</div>
                    <Badge variant="outline">优先级: {source.priority}</Badge>
                  </div>
                  <Button size="sm" variant="outline" onClick={() => testMutation.mutate(source.name)} disabled={testMutation.isPending}>
                    {testMutation.isPending ? <Loader2 className="size-4 animate-spin" /> : <RefreshCw className="size-4" />}
                    测试
                  </Button>
                </div>
                <div className="mt-2 text-sm text-muted-foreground">{source.description}</div>
                {sourceTestResults[source.name] ? (
                  <div className={`mt-3 rounded-md border p-3 text-sm ${sourceTestResults[source.name].available ? "border-emerald-200 bg-emerald-50 text-emerald-900" : "border-destructive/30 bg-destructive/5 text-destructive"}`}>
                    <div className="font-medium">最后测试结果</div>
                    <div className="mt-1">{sourceTestResults[source.name].message}</div>
                  </div>
                ) : null}
              </div>
            ))}
            {!sources.length ? <EmptyState title="暂无数据源状态" /> : null}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between gap-3">
            <CardTitle>使用建议</CardTitle>
            <Button size="sm" variant="outline" onClick={() => void recommendationsQuery.refetch()}>
              <RefreshCw className="size-4" />
              刷新
            </Button>
          </CardHeader>
          <CardContent className="space-y-5 text-sm">
            {recommendations?.primary_source ? (
              <section className="space-y-2">
                <div className="flex items-center gap-2 font-semibold"><Star className="size-4 text-amber-500" />推荐主数据源</div>
                <div className="rounded-md border border-emerald-200 bg-emerald-50 p-4">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge className="uppercase">{recommendations.primary_source.name}</Badge>
                    <span className="text-muted-foreground">优先级: {recommendations.primary_source.priority}</span>
                  </div>
                  <div className="mt-2 text-emerald-900">{recommendations.primary_source.reason}</div>
                </div>
              </section>
            ) : null}

            {recommendations?.fallback_sources?.length ? (
              <section className="space-y-2">
                <div className="font-semibold">备用数据源</div>
                <div className="space-y-2">
                  {recommendations.fallback_sources.map((source) => (
                    <div key={source.name} className="flex items-center gap-2 rounded-md border p-3">
                      <Badge variant="secondary" className="uppercase">{source.name}</Badge>
                      <span className="text-muted-foreground">优先级: {source.priority}</span>
                    </div>
                  ))}
                </div>
              </section>
            ) : null}

            {(recommendations?.suggestions || []).length ? (
              <section className="space-y-2">
                <div className="font-semibold">优化建议</div>
                {(recommendations?.suggestions || []).map((item, index) => <div key={`${item}-${index}`} className="rounded-md border p-3">{item}</div>)}
              </section>
            ) : null}

            {(recommendations?.warnings || []).length ? (
              <section className="space-y-2">
                <div className="font-semibold">注意事项</div>
                {(recommendations?.warnings || []).map((item, index) => <div key={`${item}-${index}`} className="rounded-md border border-amber-200 bg-amber-50 p-3 text-amber-900">{item}</div>)}
              </section>
            ) : null}

            <section className="space-y-3">
              <div className="font-semibold">配置示例</div>
              <div className="rounded-md border bg-muted/30 p-3">
                <div className="font-medium">环境变量配置</div>
                <pre className="mt-2 overflow-x-auto rounded bg-background p-3 text-xs"><code>{`# Tushare配置（推荐）
TUSHARE_ENABLED=true
TUSHARE_TOKEN=your_tushare_token_here

# AKShare配置
AKSHARE_ENABLED=true

# BaoStock配置
BAOSTOCK_ENABLED=true

# 默认数据源
DEFAULT_CHINA_DATA_SOURCE=${recommendations?.primary_source?.name || "tushare"}`}</code></pre>
              </div>
              <div className="rounded-md border bg-muted/30 p-3">
                <div className="font-medium">API调用示例</div>
                <pre className="mt-2 overflow-x-auto rounded bg-background p-3 text-xs"><code>{`# 使用默认优先级同步
POST /api/sync/multi-source/stock_basics/run

# 指定优先数据源
POST /api/sync/multi-source/stock_basics/run?preferred_sources=${getPreferredSourcesExample(recommendations)}

# 强制同步
POST /api/sync/multi-source/stock_basics/run?force=true`}</code></pre>
              </div>
            </section>
          </CardContent>
        </Card>
        </div>

        <div className="space-y-6">
          <Card>
            <CardHeader><CardTitle>同步控制</CardTitle></CardHeader>
            <CardContent className="space-y-6">
              <section className="space-y-3">
                <div className="font-semibold">当前状态</div>
                <div className="flex flex-wrap items-center gap-3">
                  {syncStatusBadge(status?.status)}
                  {statusQuery.isFetching ? <span className="flex items-center gap-1 text-sm text-muted-foreground"><Loader2 className="size-4 animate-spin" />刷新中</span> : null}
                </div>
                {isRunning ? (
                  <div className="space-y-2">
                    <div className="h-2 overflow-hidden rounded-full bg-muted">
                      <div className="h-full bg-primary transition-all" style={{ width: `${progress}%` }} />
                    </div>
                    <div className="text-sm text-muted-foreground">正在同步中... {status?.total ? `${processed}/${status.total}` : ""}</div>
                  </div>
                ) : null}
              </section>

              {status && status.status !== "never_run" ? (
                <section className="space-y-3">
                  <div className="font-semibold">同步统计</div>
                  <div className="grid gap-3 sm:grid-cols-4">
                    <StatCard label="总数" value={status.total ?? 0} />
                    <StatCard label="新增" value={status.inserted ?? 0} />
                    <StatCard label="更新" value={status.updated ?? 0} />
                    <StatCard label="错误" value={status.errors ?? 0} />
                  </div>
                  {status.data_sources_used?.length ? (
                    <div className="space-y-2">
                      <div className="text-sm font-medium">使用的数据源:</div>
                      <div className="flex flex-wrap gap-2">
                        {status.data_sources_used.map((source) => <Badge key={source} variant="secondary">{source}</Badge>)}
                      </div>
                    </div>
                  ) : null}
                  {status.finished_at ? <div className="text-sm text-muted-foreground">完成时间: {formatDateTime(status.finished_at)}</div> : null}
                  {status.message && status.status === "failed" ? <div className="rounded-md border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive">{status.message}</div> : null}
                </section>
              ) : null}

              <section className="space-y-4">
                <div className="font-semibold">同步操作</div>
                <div className="grid gap-3">
                  <Label>优先数据源:</Label>
                  <div className="grid gap-2 sm:grid-cols-3">
                    {sources.map((source) => (
                      <label key={source.name} className={`flex items-center gap-2 rounded-md border p-3 text-sm ${!source.available ? "cursor-not-allowed opacity-60" : ""}`}>
                        <input
                          type="checkbox"
                          disabled={!source.available}
                          checked={preferredSources.includes(source.name)}
                          onChange={(event) => {
                            setPreferredSources((value) => event.target.checked
                              ? [...value, source.name]
                              : value.filter((item) => item !== source.name))
                          }}
                        />
                        <span className="font-medium uppercase">{source.name}</span>
                        <span className="text-muted-foreground">优先级: {source.priority}</span>
                      </label>
                    ))}
                  </div>
                  <div className="text-xs text-muted-foreground">选择优先使用的数据源（可选）</div>
                </div>

                <label className="flex flex-wrap items-center gap-3 text-sm">
                  <span className="font-medium">强制同步:</span>
                  <input type="checkbox" checked={force} onChange={(event) => setForce(event.target.checked)} />
                  <span>{force ? "是" : "否"}</span>
                  <span className="text-muted-foreground">强制同步将忽略正在运行的同步任务</span>
                </label>

                <div className="flex flex-wrap gap-2">
                  <LoadingButton loading={syncMutation.isPending || isRunning} disabled={isRunning && !force} onClick={() => startSync()}>
                    <Play className="size-4" />
                    {getSyncButtonText(status, syncMutation.isPending, progress)}
                  </LoadingButton>
                  <Button variant="outline" onClick={() => void statusQuery.refetch()}>
                    <RefreshCw className="size-4" />
                    刷新状态
                  </Button>
                  <LoadingButton
                    loading={maintenanceMutation.isPending}
                    variant="outline"
                    onClick={() => setConfirm({
                      title: "确认清空缓存",
                      description: "确定要清空同步缓存吗？这将删除所有缓存的数据。",
                      confirmText: "清空缓存",
                      onConfirm: () => maintenanceMutation.mutate(() => clearSyncCache())
                    })}
                  >
                    <Trash2 className="size-4" />
                    清空缓存
                  </LoadingButton>
                  <LoadingButton loading={syncMutation.isPending} variant="outline" onClick={() => startSync(true)}>
                    <RefreshCw className="size-4" />
                    强制重新同步
                  </LoadingButton>
                </div>
              </section>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between gap-3">
              <CardTitle>同步历史</CardTitle>
              <Button size="sm" variant="outline" onClick={() => {
                setHistoryPage(1)
                void historyQuery.refetch()
              }}>
                <RefreshCw className="size-4" />
                刷新
              </Button>
            </CardHeader>
            <CardContent>
              {history.length ? (
                <div className="max-h-[600px] space-y-4 overflow-y-auto pr-1">
                  {history.map((item, index) => (
                    <div key={`${item.job}-${item.started_at || item.finished_at}-${index}`} className="border-l-2 border-border pl-4">
                      <div className="flex flex-wrap items-center gap-2">
                        <Clock className="size-4 text-muted-foreground" />
                        <span className="text-sm text-muted-foreground">{formatSyncHistoryTime(item.finished_at || item.started_at)}</span>
                        {syncStatusBadge(item.status)}
                        <span className="font-medium">{item.job}</span>
                      </div>
                      <div className="mt-2 flex flex-wrap gap-3 text-sm">
                        <span>总数: {item.total}</span>
                        <span className="text-emerald-700">新增: {item.inserted}</span>
                        <span className="text-primary">更新: {item.updated}</span>
                        <span className="text-destructive">错误: {item.errors}</span>
                      </div>
                      {item.data_sources_used?.length ? (
                        <div className="mt-2 flex flex-wrap items-center gap-2 text-sm">
                          <span className="text-muted-foreground">数据源:</span>
                          {item.data_sources_used.map((source) => <Badge key={source} variant="secondary">{source}</Badge>)}
                        </div>
                      ) : null}
                      {item.last_trade_date ? <div className="mt-2 text-sm text-muted-foreground">交易日期: {item.last_trade_date}</div> : null}
                      {item.message ? <div className={`mt-2 rounded-md border p-3 text-sm ${item.status === "failed" ? "border-destructive/30 bg-destructive/5 text-destructive" : "border-amber-200 bg-amber-50 text-amber-900"}`}>{item.message}</div> : null}
                      {getSyncDuration(item.started_at, item.finished_at) ? <div className="mt-2 text-xs text-muted-foreground">{getSyncDuration(item.started_at, item.finished_at)}</div> : null}
                    </div>
                  ))}
                  {historyHasMore ? (
                    <div className="pt-2">
                      <Button variant="outline" onClick={() => setHistoryPage((value) => value + 1)} disabled={historyQuery.isFetching}>
                        {historyQuery.isFetching ? <Loader2 className="size-4 animate-spin" /> : null}
                        加载更多
                      </Button>
                    </div>
                  ) : null}
                </div>
              ) : <EmptyState title="暂无同步历史" />}
            </CardContent>
          </Card>
        </div>
      </div>

      <Dialog open={testDialogOpen} onOpenChange={setTestDialogOpen}>
        <DialogContent className="max-w-3xl">
          <DialogHeader>
            <DialogTitle>全面测试结果</DialogTitle>
            <DialogDescription>共测试 {testResults.length} 个数据源，{testResults.filter((item) => item.available).length} 个可用。</DialogDescription>
          </DialogHeader>
          <GenericTable<DataSourceTestResult> rows={testResults} emptyText="暂无测试结果">
            <TableHeader>
              <TableRow>
                <TableHead>数据源</TableHead>
                <TableHead>优先级</TableHead>
                <TableHead>状态</TableHead>
                <TableHead>Token 来源</TableHead>
                <TableHead>消息</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {testResults.map((item) => (
                <TableRow key={item.name}>
                  <TableCell>{item.name}</TableCell>
                  <TableCell>{item.priority}</TableCell>
                  <TableCell>{boolBadge(item.available, "可用", "不可用")}</TableCell>
                  <TableCell>{item.token_source || "-"}</TableCell>
                  <TableCell>{item.message}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </GenericTable>
          <Button
            variant="outline"
            onClick={() => {
              const blob = new Blob([JSON.stringify({ exported_at: new Date().toISOString(), test_results: testResults }, null, 2)], { type: "application/json" })
              downloadBlob(blob, `sync-test-results-${new Date().toISOString().slice(0, 10)}.json`)
            }}
          >
            导出结果
          </Button>
        </DialogContent>
      </Dialog>
      <ConfirmDialog
        open={Boolean(confirm)}
        title={confirm?.title || ""}
        description={confirm?.description || ""}
        confirmText={confirm?.confirmText}
        onOpenChange={(open) => {
          if (!open) setConfirm(null)
        }}
        onConfirm={() => {
          confirm?.onConfirm()
          setConfirm(null)
        }}
      />
    </div>
  )
}

export function CacheManagementPage() {
  const [cleanupDays, setCleanupDays] = useState(7)
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState("20")
  const [confirm, setConfirm] = useState<ConfirmState>(null)
  const queryClient = useQueryClient()
  const statsQuery = useQuery({ queryKey: ["cache", "stats"], queryFn: () => getCacheStats(), retry: false })
  const detailsQuery = useQuery({ queryKey: ["cache", "details", page, pageSize], queryFn: () => getCacheDetails(page, Number(pageSize)), retry: false })
  const backendQuery = useQuery({ queryKey: ["cache", "backend"], queryFn: () => getCacheBackendInfo(), retry: false })
  const actionMutation = useMutation({
    mutationFn: async (action: () => Promise<unknown>) => action(),
    onSuccess: () => {
      toast.success("缓存操作已完成")
      void queryClient.invalidateQueries({ queryKey: ["cache"] })
    },
    onError: (error) => toast.error(error.message)
  })
  const stats = statsQuery.data
  const details = detailsQuery.data?.items || []
  const total = detailsQuery.data?.total || 0
  const totalPages = Math.max(1, Math.ceil(total / Number(pageSize)))
  const maxSize = stats?.maxSize || 1
  const usagePercent = Math.min(Math.round(((stats?.totalSize || 0) / maxSize) * 100), 100)

  return (
    <div>
      <PageHeader
        title="缓存管理"
        description="管理股票数据缓存，优化系统性能"
        actions={
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" onClick={() => void statsQuery.refetch()}>刷新统计</Button>
          </div>
        }
      />
      <div className="grid gap-4 md:grid-cols-4">
        <StatCard label="总文件数" value={stats?.totalFiles ?? 0} />
        <StatCard label="总大小" value={formatBytes(stats?.totalSize ?? 0)} />
        <StatCard label="股票数据" value={stats?.stockDataCount ?? 0} />
        <StatCard label="新闻数据" value={stats?.newsDataCount ?? 0} />
      </div>
      <Card className="mt-6">
        <CardHeader><CardTitle>缓存使用情况</CardTitle></CardHeader>
        <CardContent>
          <div className="h-3 rounded bg-muted">
            <div className="h-3 rounded bg-primary" style={{ width: `${usagePercent}%` }} />
          </div>
          <div className="mt-2 text-sm text-muted-foreground">已使用 {formatBytes(stats?.totalSize ?? 0)} / {formatBytes(maxSize)}</div>
          <div className="mt-1 text-xs text-muted-foreground">后端：{backendQuery.data?.system || "-"}，主缓存：{backendQuery.data?.primary_backend || "unknown"}，回退：{backendQuery.data?.fallback_enabled ? "启用" : "关闭"}</div>
        </CardContent>
      </Card>
      <Card className="mt-6">
        <CardHeader><CardTitle>缓存操作</CardTitle></CardHeader>
        <CardContent className="grid gap-4 md:grid-cols-3">
          <div className="rounded-md border p-4">
            <div className="text-sm font-medium">刷新统计</div>
            <p className="mt-2 text-sm text-muted-foreground">重新获取最新的缓存统计信息</p>
            <Button className="mt-3" variant="outline" onClick={() => void statsQuery.refetch()}>刷新统计</Button>
          </div>
          <div className="rounded-md border p-4">
            <div className="text-sm font-medium">清理过期缓存</div>
            <p className="mt-2 text-sm text-muted-foreground">删除指定天数之前的缓存文件</p>
            <Label htmlFor="cleanup-days" className="mt-3 block">清理天数</Label>
            <Input id="cleanup-days" className="mt-2" type="number" min={1} max={30} value={cleanupDays} onChange={(event) => setCleanupDays(Number(event.target.value) || 7)} />
            <div className="mt-2 flex flex-wrap gap-2 text-xs text-muted-foreground">
              <span>1天</span><span>1周</span><span>2周</span><span>1月</span>
            </div>
            <div className="mt-2 text-sm text-muted-foreground">将清理 {cleanupDays} 天前的缓存文件</div>
            <Button
              className="mt-3"
              variant="outline"
              onClick={() => setConfirm({
                title: "清理过期缓存",
                description: `确定要清理 ${cleanupDays} 天前的缓存吗？`,
                confirmText: "清理",
                onConfirm: () => actionMutation.mutate(() => cleanupOldCache(cleanupDays))
              })}
            >
              清理过期缓存
            </Button>
          </div>
          <div className="rounded-md border p-4">
            <div className="text-sm font-medium">清空所有缓存</div>
            <p className="mt-2 text-sm text-destructive">此操作将删除所有缓存文件，无法恢复</p>
            <Button
              className="mt-3"
              variant="destructive"
              onClick={() => setConfirm({
                title: "清空所有缓存",
                description: "确定要删除所有缓存吗？此操作不可恢复。",
                confirmText: "清空",
                onConfirm: () => actionMutation.mutate(() => clearAllCache())
              })}
            >
              清空所有缓存
            </Button>
          </div>
        </CardContent>
      </Card>
      <Card className="mt-6">
        <CardHeader className="flex flex-row items-center justify-between gap-3">
          <CardTitle>缓存详情</CardTitle>
          <div className="flex gap-2">
            <Button size="sm" variant="outline" onClick={() => void detailsQuery.refetch()}>刷新</Button>
            <Select value={pageSize} onValueChange={(value) => { setPageSize(value); setPage(1) }}>
              <SelectTrigger aria-label="缓存每页条数" className="w-36"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="10">10 条/页</SelectItem>
                <SelectItem value="20">20 条/页</SelectItem>
                <SelectItem value="50">50 条/页</SelectItem>
                <SelectItem value="100">100 条/页</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </CardHeader>
        <CardContent>
          <GenericTable<CacheDetailItem> rows={details} emptyText="暂无缓存详情">
            <TableHeader>
              <TableRow>
                <TableHead>类型</TableHead>
                <TableHead>股票代码</TableHead>
                <TableHead>大小</TableHead>
                <TableHead>创建时间</TableHead>
                <TableHead>最后访问</TableHead>
                <TableHead>命中</TableHead>
                <TableHead>操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {details.map((item) => (
                <TableRow key={`${item.type}-${item.symbol}-${item.created_at}`}>
                  <TableCell>{item.type}</TableCell>
                  <TableCell>{item.symbol}</TableCell>
                  <TableCell>{formatBytes(item.size)}</TableCell>
                  <TableCell>{formatDateTime(item.created_at)}</TableCell>
                  <TableCell>{formatDateTime(item.last_accessed)}</TableCell>
                  <TableCell>{item.hit_count}</TableCell>
                  <TableCell><Button size="sm" variant="outline" disabled>删除</Button></TableCell>
                </TableRow>
              ))}
            </TableBody>
          </GenericTable>
          <div className="mt-4 flex flex-wrap items-center justify-between gap-3 text-sm text-muted-foreground">
            <div>共 {total} 条，第 {page} / {totalPages} 页</div>
            <div className="flex gap-2">
              <Button size="sm" variant="outline" disabled={page <= 1} onClick={() => setPage((value) => Math.max(1, value - 1))}>上一页</Button>
              <Button size="sm" variant="outline" disabled={page >= totalPages} onClick={() => setPage((value) => value + 1)}>下一页</Button>
            </div>
          </div>
        </CardContent>
      </Card>
      <ConfirmDialog
        open={Boolean(confirm)}
        title={confirm?.title || ""}
        description={confirm?.description || ""}
        confirmText={confirm?.confirmText}
        destructive
        onOpenChange={(nextOpen) => {
          if (!nextOpen) setConfirm(null)
        }}
        onConfirm={() => {
          confirm?.onConfirm()
          setConfirm(null)
        }}
      />
    </div>
  )
}

export function UsageStatisticsPage() {
  const [days, setDays] = useState("7")
  const queryClient = useQueryClient()
  const statisticsQuery = useQuery({ queryKey: ["usage", "stats", days], queryFn: () => getUsageStatistics({ days: Number(days) }).then(getResponseData), retry: false })
  const recordsQuery = useQuery({ queryKey: ["usage", "records"], queryFn: () => getUsageRecords({ limit: 50 }).then(getResponseData), retry: false })
  const cleanupMutation = useMutation({
    mutationFn: () => deleteOldRecords(90),
    onSuccess: () => {
      toast.success("旧使用记录已清理")
      void queryClient.invalidateQueries({ queryKey: ["usage"] })
    },
    onError: (error) => toast.error(error.message)
  })
  const stats = statisticsQuery.data
  const records = recordsQuery.data?.records || []
  const providerOption = useMemo<EChartsOption>(() => ({
    tooltip: { trigger: "item" },
    series: [{
      type: "pie",
      data: Object.entries(stats?.by_provider || {}).map(([name, value]) => ({ name, value: numberFrom(value, "cost") }))
    }]
  }), [stats])
  const modelOption = useMemo<EChartsOption>(() => ({
    xAxis: { type: "category", data: Object.keys(stats?.by_model || {}) },
    yAxis: { type: "value" },
    series: [{ type: "bar", data: Object.values(stats?.by_model || {}).map((value) => numberFrom(value, "cost")) }]
  }), [stats])

  return (
    <div>
      <PageHeader
        title="使用统计与计费"
        description="查看 Token、成本、模型和供应商使用统计。"
        actions={
          <div className="flex gap-2">
            <Select value={days} onValueChange={setDays}>
              <SelectTrigger className="w-32"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="7">最近7天</SelectItem>
                <SelectItem value="30">最近30天</SelectItem>
                <SelectItem value="90">最近90天</SelectItem>
              </SelectContent>
            </Select>
            <Button variant="outline" onClick={() => {
              void statisticsQuery.refetch()
              void recordsQuery.refetch()
            }}>刷新</Button>
          </div>
        }
      />
      <div className="grid gap-4 md:grid-cols-4">
        <StatCard label="总请求数" value={stats?.total_requests ?? 0} />
        <StatCard label="总输入 Token" value={stats?.total_input_tokens ?? 0} />
        <StatCard label="总输出 Token" value={stats?.total_output_tokens ?? 0} />
        <StatCard label="总成本" value={Object.entries(stats?.cost_by_currency || {}).map(([currency, value]) => `${value.toFixed(4)} ${currency}`).join(" / ") || "0"} />
      </div>
      <div className="mt-6 grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader><CardTitle>按供应商统计</CardTitle></CardHeader>
          <CardContent><EChartPanel option={providerOption} empty={!Object.keys(stats?.by_provider || {}).length} height={300} /></CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle>按模型统计</CardTitle></CardHeader>
          <CardContent><EChartPanel option={modelOption} empty={!Object.keys(stats?.by_model || {}).length} height={300} /></CardContent>
        </Card>
      </div>
      <Card className="mt-6">
        <CardHeader><CardTitle>每日成本趋势</CardTitle></CardHeader>
        <CardContent className="h-[300px] text-sm text-muted-foreground">暂无每日成本趋势数据</CardContent>
      </Card>
      <Card className="mt-6">
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle>使用记录</CardTitle>
          <LoadingButton variant="destructive" size="sm" loading={cleanupMutation.isPending} onClick={() => cleanupMutation.mutate()}>清理旧记录</LoadingButton>
        </CardHeader>
        <CardContent>
          <GenericTable<UsageRecord> rows={records} emptyText="暂无使用记录">
            <TableHeader>
              <TableRow>
                <TableHead>时间</TableHead>
                <TableHead>供应商</TableHead>
                <TableHead>模型</TableHead>
                <TableHead>输入 Token</TableHead>
                <TableHead>输出 Token</TableHead>
                <TableHead>成本</TableHead>
                <TableHead>分析类型</TableHead>
                <TableHead>会话ID</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {records.map((record) => (
                <TableRow key={`${record.session_id}-${record.timestamp}`}>
                  <TableCell>{formatDateTime(record.timestamp)}</TableCell>
                  <TableCell>{record.provider}</TableCell>
                  <TableCell>{record.model_name}</TableCell>
                  <TableCell>{record.input_tokens}</TableCell>
                  <TableCell>{record.output_tokens}</TableCell>
                  <TableCell>{record.cost.toFixed(4)} {record.currency || "CNY"}</TableCell>
                  <TableCell>{record.analysis_type}</TableCell>
                  <TableCell className="max-w-[220px] truncate">{record.session_id}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </GenericTable>
        </CardContent>
      </Card>
    </div>
  )
}

export function SchedulerManagementPage() {
  const [keyword, setKeyword] = useState("")
  const [status, setStatus] = useState("all")
  const [dataSourceFilter, setDataSourceFilter] = useState("all")
  const [editingJob, setEditingJob] = useState<Job | null>(null)
  const [historyOpen, setHistoryOpen] = useState(false)
  const [executionStatus, setExecutionStatus] = useState("all")
  const [executionMode, setExecutionMode] = useState("all")
  const [selectedExecution, setSelectedExecution] = useState<JobExecution | null>(null)
  const [selectedJobDetail, setSelectedJobDetail] = useState<Job | null>(null)
  const [description, setDescription] = useState("")
  const [displayName, setDisplayName] = useState("")
  const queryClient = useQueryClient()
  const jobsQuery = useQuery({ queryKey: ["scheduler", "jobs"], queryFn: () => getJobs().then(getResponseData), retry: false })
  const statsQuery = useQuery({ queryKey: ["scheduler", "stats"], queryFn: () => getSchedulerStats().then(getResponseData), retry: false })
  const healthQuery = useQuery({ queryKey: ["scheduler", "health"], queryFn: () => getSchedulerHealth().then(getResponseData), retry: false })
  const executionsQuery = useQuery({
    queryKey: ["scheduler", "executions", executionStatus, executionMode],
    queryFn: () => getJobExecutions({
      status: executionStatus === "all" ? undefined : executionStatus as "success" | "failed" | "missed" | "running",
      is_manual: executionMode === "all" ? undefined : executionMode === "manual",
      limit: 50,
      offset: 0
    }).then(getResponseData),
    enabled: historyOpen,
    retry: false
  })
  const actionMutation = useMutation({
    mutationFn: async (action: () => Promise<unknown>) => action(),
    onSuccess: () => {
      toast.success("调度任务已更新")
      void queryClient.invalidateQueries({ queryKey: ["scheduler"] })
      setEditingJob(null)
    },
    onError: (error) => toast.error(error.message)
  })
  const executionMutation = useMutation({
    mutationFn: async (action: () => Promise<unknown>) => action(),
    onSuccess: () => {
      toast.success("执行记录已更新")
      void queryClient.invalidateQueries({ queryKey: ["scheduler", "executions"] })
    },
    onError: (error) => toast.error(error.message)
  })

  const jobs = (jobsQuery.data || []).filter((job) => {
    const matchesKeyword = job.name.toLowerCase().includes(keyword.toLowerCase()) || (job.display_name || "").toLowerCase().includes(keyword.toLowerCase())
    const matchesStatus = status === "all" || (status === "running" ? !job.paused : job.paused)
    const sourceText = `${job.name} ${job.display_name || ""} ${job.description || ""}`.toLowerCase()
    const matchesSource = dataSourceFilter === "all" || sourceText.includes(dataSourceFilter.toLowerCase())
    return matchesKeyword && matchesStatus && matchesSource
  })
  const stats = statsQuery.data
  const health = healthQuery.data
  const executions = executionsQuery.data?.items || []

  return (
    <div>
      <PageHeader
        title="定时任务管理"
        description="管理系统中的所有定时任务，支持暂停、恢复和手动触发"
        actions={
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" onClick={() => void jobsQuery.refetch()}>刷新</Button>
            <Button variant="outline" onClick={() => setHistoryOpen(true)}>执行历史</Button>
          </div>
        }
      />
      <div className="grid gap-4 md:grid-cols-4">
        <StatCard label="总任务数" value={stats?.total_jobs ?? 0} />
        <StatCard label="运行中" value={stats?.running_jobs ?? 0} />
        <StatCard label="已暂停" value={stats?.paused_jobs ?? 0} />
        <StatCard label="调度器" value={health?.status || "unknown"} />
      </div>
      <Card className="mt-6">
        <CardHeader><CardTitle>搜索和筛选</CardTitle></CardHeader>
        <CardContent className="grid gap-3 md:grid-cols-4">
          <div className="space-y-2">
            <Label>任务名称</Label>
          <Input placeholder="搜索任务名称" value={keyword} onChange={(event) => setKeyword(event.target.value)} />
          </div>
          <div className="space-y-2">
            <Label>数据源</Label>
            <Select value={dataSourceFilter} onValueChange={setDataSourceFilter}>
              <SelectTrigger><SelectValue placeholder="全部数据源" /></SelectTrigger>
              <SelectContent>
                <SelectItem value="all">全部数据源</SelectItem>
                <SelectItem value="Tushare">Tushare</SelectItem>
                <SelectItem value="AKShare">AKShare</SelectItem>
                <SelectItem value="BaoStock">BaoStock</SelectItem>
                <SelectItem value="多数据源">多数据源</SelectItem>
                <SelectItem value="其他">其他</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label>状态</Label>
          <Select value={status} onValueChange={setStatus}>
            <SelectTrigger><SelectValue placeholder="全部状态" /></SelectTrigger>
            <SelectContent>
              <SelectItem value="all">全部状态</SelectItem>
              <SelectItem value="running">运行中</SelectItem>
              <SelectItem value="paused">已暂停</SelectItem>
            </SelectContent>
          </Select>
          </div>
          <Button variant="outline" className="self-end" onClick={() => {
            setKeyword("")
            setStatus("all")
            setDataSourceFilter("all")
          }}>重置</Button>
        </CardContent>
      </Card>
      <Card className="mt-6">
        <CardHeader><CardTitle>任务列表</CardTitle></CardHeader>
        <CardContent>
          <GenericTable<Job> rows={jobs} emptyText="暂无定时任务">
            <TableHeader>
              <TableRow>
                <TableHead>任务名称</TableHead>
                <TableHead>触发器名称</TableHead>
                <TableHead>触发器</TableHead>
                <TableHead>备注</TableHead>
                <TableHead>下次执行时间</TableHead>
                <TableHead>操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {jobs.map((job) => (
                <TableRow key={job.id}>
                  <TableCell>
                    <div className="flex items-center gap-2">
                      {boolBadge(!job.paused, "运行中", "已暂停")}
                      <span className="font-medium">{job.name}</span>
                    </div>
                  </TableCell>
                  <TableCell>{job.display_name || "-"}</TableCell>
                  <TableCell className="text-xs text-muted-foreground">{job.trigger}</TableCell>
                  <TableCell className="max-w-[260px] truncate">{job.description || "-"}</TableCell>
                  <TableCell>{job.next_run_time ? formatDateTime(job.next_run_time) : "-"}</TableCell>
                  <TableCell>
                    <div className="flex flex-wrap gap-2">
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => {
                          setEditingJob(job)
                          setDisplayName(job.display_name || "")
                          setDescription(job.description || "")
                        }}
                      >
                        编辑
                      </Button>
                      <Button size="sm" variant="outline" onClick={() => actionMutation.mutate(() => job.paused ? resumeJob(job.id) : pauseJob(job.id))}>
                        {job.paused ? "恢复" : "暂停"}
                      </Button>
                      <Button size="sm" onClick={() => actionMutation.mutate(() => triggerJob(job.id, true))}>立即执行</Button>
                      <Button size="sm" variant="outline" onClick={() => setSelectedJobDetail(job)}>详情</Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </GenericTable>
        </CardContent>
      </Card>
      <Dialog open={Boolean(selectedJobDetail)} onOpenChange={(nextOpen) => !nextOpen && setSelectedJobDetail(null)}>
        <DialogContent className="max-w-3xl">
          <DialogHeader>
            <DialogTitle>任务详情</DialogTitle>
            <DialogDescription>{selectedJobDetail?.name || ""}</DialogDescription>
          </DialogHeader>
          <div className="grid gap-3 text-sm">
            <div>任务ID：{selectedJobDetail?.id || "-"}</div>
            <div>任务名称：{selectedJobDetail?.name || "-"}</div>
            <div>状态：{selectedJobDetail ? (selectedJobDetail.paused ? "已暂停" : "运行中") : "-"}</div>
            <div>触发器：{selectedJobDetail?.trigger || "-"}</div>
            <div>下次执行时间：{selectedJobDetail?.next_run_time ? formatDateTime(selectedJobDetail.next_run_time) : "已暂停"}</div>
            {selectedJobDetail?.func ? <div>执行函数：{selectedJobDetail.func}</div> : null}
            {selectedJobDetail?.kwargs ? <pre className="overflow-auto rounded-md bg-muted p-3 text-xs">参数：{JSON.stringify(selectedJobDetail.kwargs, null, 2)}</pre> : null}
          </div>
        </DialogContent>
      </Dialog>
      <Dialog open={Boolean(editingJob)} onOpenChange={(nextOpen) => !nextOpen && setEditingJob(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>编辑任务信息</DialogTitle>
            <DialogDescription>更新触发器显示名称和备注。</DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="grid gap-2">
              <Label htmlFor="job-display-name">触发器名称</Label>
              <Input id="job-display-name" value={displayName} onChange={(event) => setDisplayName(event.target.value)} />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="job-description">备注</Label>
              <textarea
                id="job-description"
                value={description}
                onChange={(event) => setDescription(event.target.value)}
                className="min-h-24 rounded-md border bg-background px-3 py-2 text-sm"
              />
            </div>
            <LoadingButton loading={actionMutation.isPending} onClick={() => editingJob && actionMutation.mutate(() => updateJobMetadata(editingJob.id, { display_name: displayName, description }))}>
              保存
            </LoadingButton>
          </div>
        </DialogContent>
      </Dialog>
      <Dialog open={historyOpen} onOpenChange={setHistoryOpen}>
        <DialogContent className="max-w-6xl">
          <DialogHeader>
            <DialogTitle>执行历史</DialogTitle>
            <DialogDescription>查看手动和自动执行记录，可终止运行中任务、标记失败或删除记录。</DialogDescription>
          </DialogHeader>
          <div className="grid gap-3 md:grid-cols-3">
            <Select value={executionStatus} onValueChange={setExecutionStatus}>
              <SelectTrigger aria-label="执行状态"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="all">全部状态</SelectItem>
                <SelectItem value="running">执行中</SelectItem>
                <SelectItem value="success">成功</SelectItem>
                <SelectItem value="failed">失败</SelectItem>
                <SelectItem value="missed">错过</SelectItem>
              </SelectContent>
            </Select>
            <Select value={executionMode} onValueChange={setExecutionMode}>
              <SelectTrigger aria-label="执行来源"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="all">全部来源</SelectItem>
                <SelectItem value="manual">手动触发</SelectItem>
                <SelectItem value="auto">自动执行</SelectItem>
              </SelectContent>
            </Select>
            <Button variant="outline" onClick={() => void executionsQuery.refetch()}>刷新</Button>
          </div>
          <GenericTable<JobExecution> rows={executions} emptyText="暂无执行记录">
            <TableHeader>
              <TableRow>
                <TableHead>任务</TableHead>
                <TableHead>状态</TableHead>
                <TableHead>来源</TableHead>
                <TableHead>开始时间</TableHead>
                <TableHead>耗时</TableHead>
                <TableHead>进度</TableHead>
                <TableHead>操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {executions.map((item) => (
                <TableRow key={item._id}>
                  <TableCell>
                    <div className="font-medium">{item.job_name || item.job_id}</div>
                    <div className="text-xs text-muted-foreground">{item.current_item || item.progress_message || item.job_id}</div>
                  </TableCell>
                  <TableCell>{item.status}</TableCell>
                  <TableCell>{item.is_manual ? "手动" : "自动"}</TableCell>
                  <TableCell>{formatDateTime(item.timestamp || item.scheduled_time)}</TableCell>
                  <TableCell>{typeof item.execution_time === "number" ? `${item.execution_time.toFixed(2)}s` : "-"}</TableCell>
                  <TableCell>{typeof item.progress === "number" ? `${item.progress}%` : "-"}</TableCell>
                  <TableCell>
                    <div className="flex flex-wrap gap-2">
                      <Button size="sm" variant="outline" onClick={() => setSelectedExecution(item)}>详情</Button>
                      {item.status === "running" ? <Button size="sm" variant="outline" onClick={() => executionMutation.mutate(() => cancelExecution(item._id))}>终止</Button> : null}
                      {item.status !== "failed" ? <Button size="sm" variant="outline" onClick={() => executionMutation.mutate(() => markExecutionFailed(item._id))}>标失败</Button> : null}
                      <Button size="sm" variant="destructive" onClick={() => executionMutation.mutate(() => deleteExecution(item._id))}>删除</Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </GenericTable>
        </DialogContent>
      </Dialog>
      <Dialog open={Boolean(selectedExecution)} onOpenChange={(nextOpen) => !nextOpen && setSelectedExecution(null)}>
        <DialogContent className="max-w-3xl">
          <DialogHeader>
            <DialogTitle>执行详情</DialogTitle>
            <DialogDescription>{selectedExecution?.job_name || selectedExecution?.job_id || ""}</DialogDescription>
          </DialogHeader>
          <div className="grid gap-3 text-sm md:grid-cols-2">
            <div>状态：{selectedExecution?.status || "-"}</div>
            <div>计划时间：{selectedExecution?.scheduled_time ? formatDateTime(selectedExecution.scheduled_time) : "-"}</div>
            <div>开始时间：{selectedExecution?.timestamp ? formatDateTime(selectedExecution.timestamp) : "-"}</div>
            <div>更新时间：{selectedExecution?.updated_at ? formatDateTime(selectedExecution.updated_at) : "-"}</div>
            <div>进度：{typeof selectedExecution?.progress === "number" ? `${selectedExecution.progress}%` : "-"}</div>
            <div>当前项目：{selectedExecution?.current_item || "-"}</div>
          </div>
          {selectedExecution?.return_value ? <pre className="max-h-40 overflow-auto rounded-md bg-muted p-3 text-xs">{selectedExecution.return_value}</pre> : null}
          {selectedExecution?.error_message ? <pre className="max-h-40 overflow-auto rounded-md bg-destructive/10 p-3 text-xs text-destructive">{selectedExecution.error_message}</pre> : null}
          {selectedExecution?.traceback ? <pre className="max-h-64 overflow-auto rounded-md bg-muted p-3 text-xs">{selectedExecution.traceback}</pre> : null}
        </DialogContent>
      </Dialog>
    </div>
  )
}
