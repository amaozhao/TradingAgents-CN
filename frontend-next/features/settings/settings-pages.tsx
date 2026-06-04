"use client"

import Link from "next/link"
import { useMemo, useState } from "react"
import { zodResolver } from "@hookform/resolvers/zod"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import type { EChartsOption } from "echarts"
import {
  Database,
  Download,
  FileText,
  HardDrive,
  ListChecks,
  Loader2,
  RefreshCw,
  Settings,
  Timer,
  Trash2
} from "lucide-react"
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
import { configApi, type DataSourceConfig, type DatabaseConfig, type LLMConfig, type LLMProvider } from "@/libs/api/config"
import { databaseApi, formatBytes, type DatabaseStatus } from "@/libs/api/database"
import { LogsApi, type LogFileInfo } from "@/libs/api/logs"
import { ActionTypes, getActionTypeName, OperationLogsApi, type OperationLog } from "@/libs/api/operation-logs"
import {
  getDataSourcesStatus,
  getSyncHistory,
  getSyncRecommendations,
  getSyncStatus,
  runStockBasicsSync,
  testDataSources,
  type SyncStatus
} from "@/libs/api/sync"
import {
  getJobs,
  getSchedulerHealth,
  getSchedulerStats,
  pauseJob,
  resumeJob,
  triggerJob,
  updateJobMetadata,
  type Job
} from "@/libs/api/scheduler"
import { deleteOldRecords, getUsageRecords, getUsageStatistics, type UsageRecord } from "@/libs/api/usage"
import { formatDateTime } from "@/libs/utils/datetime"

const settingsLinks = [
  { href: "/settings/config", title: "配置管理", icon: Settings, description: "大模型、数据源、数据库和系统设置" },
  { href: "/settings/database", title: "数据库管理", icon: Database, description: "数据库状态、导入导出和清理" },
  { href: "/settings/logs", title: "操作日志", icon: ListChecks, description: "用户操作记录、过滤和统计" },
  { href: "/settings/system-logs", title: "系统日志", icon: FileText, description: "后端日志文件读取、筛选和导出" },
  { href: "/settings/sync", title: "多数据源同步", icon: RefreshCw, description: "同步状态、建议、历史和手动同步" },
  { href: "/settings/cache", title: "缓存管理", icon: Trash2, description: "缓存统计、详情和清理" },
  { href: "/settings/usage", title: "使用统计", icon: HardDrive, description: "Token、成本和模型使用记录" },
  { href: "/settings/scheduler", title: "定时任务", icon: Timer, description: "调度任务、执行历史和健康状态" }
]

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
  children
}: {
  rows: T[]
  emptyText: string
  children: React.ReactNode
}) {
  if (!rows.length) {
    return <EmptyState title={emptyText} className="rounded-md border p-8" />
  }
  return (
    <div className="overflow-x-auto rounded-md border">
      <Table>{children}</Table>
    </div>
  )
}

export function SettingsIndexPage() {
  return (
    <div>
      <PageHeader title="设置" description="管理系统配置、数据源、日志、缓存、同步和调度任务。" />
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {settingsLinks.map((item) => {
          const Icon = item.icon
          return (
            <Link key={item.href} href={item.href} className="rounded-md border bg-background p-5 transition-colors hover:bg-muted">
              <Icon className="mb-4 size-5 text-primary" />
              <div className="font-medium">{item.title}</div>
              <p className="mt-2 text-sm text-muted-foreground">{item.description}</p>
            </Link>
          )
        })}
      </div>
    </div>
  )
}

export function ConfigManagementPage() {
  const queryClient = useQueryClient()
  const [open, setOpen] = useState(false)
  const [confirm, setConfirm] = useState<ConfirmState>(null)
  const [modelDialogOpen, setModelDialogOpen] = useState(false)
  const [dataSourceDialogOpen, setDataSourceDialogOpen] = useState(false)
  const [marketDialogOpen, setMarketDialogOpen] = useState(false)
  const [groupingDialogOpen, setGroupingDialogOpen] = useState(false)
  const [modelForm, setModelForm] = useState({ provider: "", provider_name: "", model_name: "" })
  const [dataSourceForm, setDataSourceForm] = useState({ name: "", type: "stock", display_name: "", priority: 1 })
  const [marketForm, setMarketForm] = useState({ id: "", name: "", display_name: "", sort_order: 1 })
  const [groupingForm, setGroupingForm] = useState({ data_source_name: "", market_category_id: "", priority: 1 })

  const providersQuery = useQuery({ queryKey: ["config", "llm-providers"], queryFn: () => configApi.getLLMProviders(), retry: false })
  const llmQuery = useQuery({ queryKey: ["config", "llm"], queryFn: () => configApi.getLLMConfigs(), retry: false })
  const dataSourceQuery = useQuery({ queryKey: ["config", "datasources"], queryFn: () => configApi.getDataSourceConfigs(), retry: false })
  const marketQuery = useQuery({ queryKey: ["config", "market-categories"], queryFn: () => configApi.getMarketCategories(), retry: false })
  const databaseQuery = useQuery({ queryKey: ["config", "database"], queryFn: () => configApi.getDatabaseConfigs(), retry: false })
  const settingsQuery = useQuery({ queryKey: ["config", "settings"], queryFn: () => configApi.getSystemSettings(), retry: false })
  const modelCatalogQuery = useQuery({ queryKey: ["config", "model-catalog"], queryFn: () => configApi.getModelCatalog(), retry: false })
  const groupingsQuery = useQuery({ queryKey: ["config", "datasource-groupings"], queryFn: () => configApi.getDataSourceGroupings(), retry: false })

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

  const addProviderMutation = useMutation({
    mutationFn: (values: ProviderFormValues) => configApi.addLLMProvider(values as Partial<LLMProvider> & { api_key?: string }),
    onSuccess: () => {
      toast.success("厂家已保存")
      setOpen(false)
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
  const settings = settingsQuery.data || {}
  const catalog = modelCatalogQuery.data || []
  const groupings = groupingsQuery.data || []

  const providerModelCount = useMemo(() => {
    const counts = new Map<string, number>()
    llmConfigs.forEach((item) => counts.set(item.provider, (counts.get(item.provider) || 0) + 1))
    return counts
  }, [llmConfigs])

  return (
    <div>
      <PageHeader
        title="配置管理"
        description="管理大模型厂家、模型目录、数据源、市场分类、数据库和系统设置。"
        actions={<Button onClick={() => setOpen(true)}>新增厂家</Button>}
      />

      <Tabs defaultValue="providers" className="space-y-4">
        <TabsList className="flex h-auto flex-wrap justify-start">
          <TabsTrigger value="providers">厂家</TabsTrigger>
          <TabsTrigger value="models">模型</TabsTrigger>
          <TabsTrigger value="datasources">数据源</TabsTrigger>
          <TabsTrigger value="markets">市场分类</TabsTrigger>
          <TabsTrigger value="database">数据库</TabsTrigger>
          <TabsTrigger value="settings">系统设置</TabsTrigger>
        </TabsList>

        <TabsContent value="providers">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle>大模型厂家</CardTitle>
              <div className="flex gap-2">
                <Button variant="outline" size="sm" onClick={() => actionMutation.mutate(() => configApi.migrateEnvToProviders())}>迁移环境变量</Button>
                <Button variant="outline" size="sm" onClick={() => actionMutation.mutate(() => configApi.initAggregatorProviders())}>初始化聚合渠道</Button>
              </div>
            </CardHeader>
            <CardContent>
              <GenericTable<LLMProvider> rows={providers} emptyText="暂无厂家配置">
                <TableHeader>
                  <TableRow>
                    <TableHead>厂家</TableHead>
                    <TableHead>密钥</TableHead>
                    <TableHead>模型数</TableHead>
                    <TableHead>状态</TableHead>
                    <TableHead>操作</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {providers.map((provider) => (
                    <TableRow key={provider.id}>
                      <TableCell>
                        <div className="font-medium">{provider.display_name || provider.name}</div>
                        <div className="text-xs text-muted-foreground">{provider.name}</div>
                        <div className="text-xs text-muted-foreground">{provider.description || "暂无描述"}</div>
                      </TableCell>
                      <TableCell>{provider.extra_config?.has_api_key ? "已配置" : "未配置"}</TableCell>
                      <TableCell>{providerModelCount.get(provider.name) || 0}</TableCell>
                      <TableCell>{boolBadge(provider.is_active)}</TableCell>
                      <TableCell>
                        <div className="flex flex-wrap gap-2">
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

        <TabsContent value="models">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle>模型配置与目录</CardTitle>
              <div className="flex gap-2">
                <Button variant="outline" size="sm" onClick={() => setModelDialogOpen(true)}>新增模型目录</Button>
                <Button variant="outline" size="sm" onClick={() => actionMutation.mutate(() => configApi.initModelCatalog())}>初始化模型目录</Button>
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

              <div className="grid gap-4 md:grid-cols-2">
                {catalog.map((item) => (
                  <div key={item.provider} className="rounded-md border p-4">
                    <div className="font-medium">{item.provider_name}</div>
                    <div className="mt-1 text-sm text-muted-foreground">{item.provider} / {item.models.length} 个模型</div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="datasources">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle>数据源配置</CardTitle>
              <Button variant="outline" size="sm" onClick={() => setDataSourceDialogOpen(true)}>新增数据源</Button>
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
        </TabsContent>

        <TabsContent value="markets">
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
                  {marketCategories.map((category) => (
                    <TableRow key={category.id}>
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
                    {groupings.map((grouping) => (
                      <TableRow key={`${grouping.market_category_id}-${grouping.data_source_name}`}>
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

        <TabsContent value="database">
          <Card>
            <CardHeader><CardTitle>数据库配置</CardTitle></CardHeader>
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
                        <Button variant="outline" size="sm" onClick={() => actionMutation.mutate(() => configApi.testDatabaseConfig(database.name))}>测试连接</Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </GenericTable>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="settings">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle>系统设置</CardTitle>
              <Button variant="outline" size="sm" onClick={() => actionMutation.mutate(() => configApi.reloadConfig())}>重新加载配置</Button>
            </CardHeader>
            <CardContent className="grid gap-3 md:grid-cols-2">
              {Object.entries(settings).slice(0, 24).map(([key, value]) => (
                <div key={key} className="rounded-md border p-3">
                  <div className="text-sm font-medium">{key}</div>
                  <div className="mt-1 truncate text-xs text-muted-foreground">{String(value)}</div>
                </div>
              ))}
              {!Object.keys(settings).length ? <EmptyState title="暂无系统设置" className="md:col-span-2" /> : null}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>新增厂家</DialogTitle>
            <DialogDescription>添加新的大模型服务厂家配置。</DialogDescription>
          </DialogHeader>
          <form className="space-y-4" onSubmit={form.handleSubmit((values) => addProviderMutation.mutate(values))}>
            <div className="grid gap-2">
              <Label htmlFor="provider-id">厂家 ID</Label>
              <Input id="provider-id" aria-label="厂家 ID" placeholder="dashscope" {...form.register("id")} />
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
              <Input id="provider-api-key" type="password" aria-label="API 密钥" {...form.register("api_key")} />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="provider-base-url">默认 Base URL</Label>
              <Input id="provider-base-url" aria-label="默认 Base URL" {...form.register("default_base_url")} />
            </div>
            <LoadingButton type="submit" loading={addProviderMutation.isPending}>保存</LoadingButton>
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
            <DialogTitle>新增数据源</DialogTitle>
            <DialogDescription>创建股票数据源配置。</DialogDescription>
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
                  await configApi.addDataSourceConfig({
                    name: dataSourceForm.name,
                    type: dataSourceForm.type,
                    display_name: dataSourceForm.display_name || dataSourceForm.name,
                    priority: dataSourceForm.priority,
                    timeout: 30,
                    rate_limit: 100,
                    enabled: true,
                    config_params: {}
                  })
                  setDataSourceDialogOpen(false)
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
                {dataSources.map((source) => <SelectItem key={source.name} value={source.name}>{source.display_name || source.name}</SelectItem>)}
              </SelectContent>
            </Select>
            <Select value={groupingForm.market_category_id || undefined} onValueChange={(value) => setGroupingForm((formValue) => ({ ...formValue, market_category_id: value }))}>
              <SelectTrigger><SelectValue placeholder="选择市场分类" /></SelectTrigger>
              <SelectContent>
                {marketCategories.map((category) => <SelectItem key={category.id} value={category.id}>{category.display_name}</SelectItem>)}
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

  const status = statusQuery.data
  const stats = statsQuery.data

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
        description="查看数据库状态、统计、导入导出和清理操作。"
        actions={<LoadingButton variant="outline" loading={statusQuery.isFetching} onClick={() => void statusQuery.refetch()}>刷新状态</LoadingButton>}
      />
      <div className="grid gap-4 md:grid-cols-2">
        {renderConnection("PostgreSQL", status?.postgres)}
        {renderConnection("Redis", status?.redis)}
      </div>
      <div className="mt-4 grid gap-4 md:grid-cols-3">
        <StatCard label="集合数" value={stats?.total_collections ?? 0} />
        <StatCard label="文档数" value={stats?.total_documents ?? 0} />
        <StatCard label="数据库大小" value={formatBytes(stats?.total_size ?? 0)} />
      </div>
      <Card className="mt-6">
        <CardHeader><CardTitle>数据管理操作</CardTitle></CardHeader>
        <CardContent className="grid gap-4 md:grid-cols-3">
          <LoadingButton loading={actionMutation.isPending} onClick={() => actionMutation.mutate(() => databaseApi.testConnections())}>测试连接</LoadingButton>
          <Button
            variant="outline"
            onClick={async () => {
              try {
                const blob = await databaseApi.exportData({ collections: ["config_and_reports"], format: "json", sanitize: true })
                downloadBlob(blob, `trading-agents-data-${new Date().toISOString().slice(0, 10)}.json`)
              } catch (error) {
                toast.error(error instanceof Error ? error.message : "导出失败")
              }
            }}
          >
            <Download className="mr-2 size-4" />导出数据
          </Button>
          <div className="flex gap-2">
            <Input aria-label="清理天数" type="number" min={1} max={365} value={cleanupDays} onChange={(event) => setCleanupDays(Number(event.target.value) || 30)} />
            <Button
              variant="destructive"
              onClick={() => setConfirm({
                title: "清理过期分析结果",
                description: `确定要删除 ${cleanupDays} 天前的分析结果吗？此操作不可恢复。`,
                confirmText: "清理",
                onConfirm: () => actionMutation.mutate(() => databaseApi.cleanupAnalysisResults(cleanupDays))
              })}
            >
              清理
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
  const [confirm, setConfirm] = useState<ConfirmState>(null)
  const queryClient = useQueryClient()

  const logsQuery = useQuery({
    queryKey: ["operation-logs", keyword, actionType, success],
    queryFn: () => OperationLogsApi.getOperationLogs({
      page: 1,
      page_size: 50,
      keyword: keyword || undefined,
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
  const stats = statsQuery.data

  return (
    <div>
      <PageHeader
        title="操作日志"
        description="查看用户操作日志、行为统计和清理记录。"
        actions={<Button variant="outline" onClick={() => void logsQuery.refetch()}>刷新</Button>}
      />
      <div className="grid gap-4 md:grid-cols-4">
        <StatCard label="总日志数" value={stats?.total_logs ?? 0} />
        <StatCard label="成功操作" value={stats?.success_logs ?? 0} />
        <StatCard label="失败操作" value={stats?.failed_logs ?? 0} />
        <StatCard label="成功率" value={`${stats?.success_rate ?? 0}%`} />
      </div>
      <Card className="mt-6">
        <CardHeader><CardTitle>筛选</CardTitle></CardHeader>
        <CardContent className="grid gap-3 md:grid-cols-4">
          <Input placeholder="搜索操作内容" value={keyword} onChange={(event) => setKeyword(event.target.value)} />
          <Select value={actionType} onValueChange={setActionType}>
            <SelectTrigger><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="all">全部类型</SelectItem>
              {Object.values(ActionTypes).map((type) => <SelectItem key={type} value={type}>{getActionTypeName(type)}</SelectItem>)}
            </SelectContent>
          </Select>
          <Select value={success} onValueChange={setSuccess}>
            <SelectTrigger><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="all">全部状态</SelectItem>
              <SelectItem value="success">成功</SelectItem>
              <SelectItem value="failed">失败</SelectItem>
            </SelectContent>
          </Select>
          <Button
            variant="destructive"
            onClick={() => setConfirm({
              title: "清空操作日志",
              description: "确定要清空当前操作日志吗？此操作不可恢复。",
              confirmText: "清空",
              onConfirm: () => clearMutation.mutate()
            })}
          >
            清空日志
          </Button>
        </CardContent>
      </Card>
      <Card className="mt-6">
        <CardHeader><CardTitle>日志列表</CardTitle></CardHeader>
        <CardContent>
          <GenericTable<OperationLog> rows={logs} emptyText="暂无操作日志">
            <TableHeader>
              <TableRow>
                <TableHead>时间</TableHead>
                <TableHead>类型</TableHead>
                <TableHead>操作</TableHead>
                <TableHead>状态</TableHead>
                <TableHead>耗时</TableHead>
                <TableHead>IP</TableHead>
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
                </TableRow>
              ))}
            </TableBody>
          </GenericTable>
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

export function SystemLogsPage() {
  const [keyword, setKeyword] = useState("")
  const [selectedFile, setSelectedFile] = useState<LogFileInfo | null>(null)
  const [confirm, setConfirm] = useState<ConfirmState>(null)
  const queryClient = useQueryClient()

  const filesQuery = useQuery({ queryKey: ["system-logs", "files"], queryFn: () => LogsApi.listLogFiles(), retry: false })
  const statsQuery = useQuery({ queryKey: ["system-logs", "stats"], queryFn: () => LogsApi.getStatistics(7), retry: false })
  const contentQuery = useQuery({
    queryKey: ["system-logs", "content", selectedFile?.name],
    queryFn: () => LogsApi.readLogFile({ filename: selectedFile?.name || "", lines: 1000 }),
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
        title="系统日志"
        description="读取、筛选、导出和删除后端系统日志文件。"
        actions={<Button variant="outline" onClick={() => void filesQuery.refetch()}>刷新</Button>}
      />
      <div className="grid gap-4 md:grid-cols-3">
        <StatCard label="日志文件数" value={stats?.total_files ?? 0} />
        <StatCard label="总大小 MB" value={stats?.total_size_mb?.toFixed?.(2) ?? 0} />
        <StatCard label="错误日志文件" value={stats?.error_files ?? 0} />
      </div>
      <Card className="mt-6">
        <CardHeader><CardTitle>日志文件列表</CardTitle></CardHeader>
        <CardContent className="space-y-4">
          <Input placeholder="搜索文件名" value={keyword} onChange={(event) => setKeyword(event.target.value)} />
          <GenericTable<LogFileInfo> rows={files} emptyText="暂无日志文件">
            <TableHeader>
              <TableRow>
                <TableHead>文件名</TableHead>
                <TableHead>类型</TableHead>
                <TableHead>大小</TableHead>
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
                      <Button size="sm" variant="outline" onClick={() => setSelectedFile(file)}>查看</Button>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={async () => {
                          const blob = await LogsApi.exportLogs({ filenames: [file.name], format: "txt" })
                          downloadBlob(blob, `${file.name}.txt`)
                        }}
                      >
                        导出
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
            <DialogDescription>显示最近 1000 行日志内容。</DialogDescription>
          </DialogHeader>
          <pre className="max-h-[60vh] overflow-auto rounded-md bg-muted p-4 text-xs">
            {(contentQuery.data?.lines || []).join("\n") || "暂无日志内容"}
          </pre>
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

export function SyncManagementPage() {
  const [force, setForce] = useState(false)
  const queryClient = useQueryClient()
  const statusQuery = useQuery({ queryKey: ["sync", "status"], queryFn: () => getSyncStatus().then(getResponseData), retry: false })
  const sourcesQuery = useQuery({ queryKey: ["sync", "sources"], queryFn: () => getDataSourcesStatus().then(getResponseData), retry: false })
  const recommendationsQuery = useQuery({ queryKey: ["sync", "recommendations"], queryFn: () => getSyncRecommendations().then(getResponseData), retry: false })
  const historyQuery = useQuery({ queryKey: ["sync", "history"], queryFn: () => getSyncHistory({ page: 1, page_size: 20 }).then(getResponseData), retry: false })

  const syncMutation = useMutation({
    mutationFn: () => runStockBasicsSync({ force }).then(getResponseData),
    onSuccess: () => {
      toast.success("同步任务已启动")
      void queryClient.invalidateQueries({ queryKey: ["sync"] })
    },
    onError: (error) => toast.error(error.message)
  })
  const testMutation = useMutation({
    mutationFn: () => testDataSources().then(getResponseData),
    onSuccess: (data) => toast.success(`测试完成：${data.test_results.filter((item) => item.available).length}/${data.test_results.length} 可用`),
    onError: (error) => toast.error(error.message)
  })

  const status = statusQuery.data
  const sources = sourcesQuery.data || []
  const history = historyQuery.data?.records || []
  const recommendations = recommendationsQuery.data

  return (
    <div>
      <PageHeader
        title="多数据源同步"
        description="查看同步状态、数据源健康、同步建议和历史记录。"
        actions={<LoadingButton loading={testMutation.isPending} variant="outline" onClick={() => testMutation.mutate()}>全面测试</LoadingButton>}
      />
      <div className="grid gap-4 md:grid-cols-4">
        <StatCard label="当前状态" value={status?.status || "unknown"} />
        <StatCard label="总数" value={status?.total ?? 0} />
        <StatCard label="新增" value={status?.inserted ?? 0} />
        <StatCard label="更新" value={status?.updated ?? 0} />
      </div>
      <Card className="mt-6">
        <CardHeader><CardTitle>同步控制</CardTitle></CardHeader>
        <CardContent className="flex flex-wrap items-center gap-3">
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={force} onChange={(event) => setForce(event.target.checked)} />
            强制同步
          </label>
          <LoadingButton loading={syncMutation.isPending} onClick={() => syncMutation.mutate()}>运行股票基础信息同步</LoadingButton>
        </CardContent>
      </Card>
      <div className="mt-6 grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader><CardTitle>数据源状态</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            {sources.map((source) => (
              <div key={source.name} className="rounded-md border p-3">
                <div className="flex items-center justify-between">
                  <div className="font-medium">{source.name}</div>
                  {boolBadge(source.available, "可用", "不可用")}
                </div>
                <div className="mt-1 text-sm text-muted-foreground">优先级 {source.priority} / {source.description}</div>
              </div>
            ))}
            {!sources.length ? <EmptyState title="暂无数据源状态" /> : null}
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle>同步建议</CardTitle></CardHeader>
          <CardContent className="space-y-3 text-sm">
            <div>主数据源：{recommendations?.primary_source?.name || "-"}</div>
            {(recommendations?.suggestions || []).map((item) => <div key={item} className="rounded-md border p-3">{item}</div>)}
            {(recommendations?.warnings || []).map((item) => <div key={item} className="rounded-md border border-destructive/30 p-3 text-destructive">{item}</div>)}
          </CardContent>
        </Card>
      </div>
      <Card className="mt-6">
        <CardHeader><CardTitle>同步历史</CardTitle></CardHeader>
        <CardContent>
          <GenericTable<SyncStatus> rows={history} emptyText="暂无同步历史">
            <TableHeader>
              <TableRow>
                <TableHead>任务</TableHead>
                <TableHead>状态</TableHead>
                <TableHead>开始时间</TableHead>
                <TableHead>结束时间</TableHead>
                <TableHead>错误数</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {history.map((item) => (
                <TableRow key={`${item.job}-${item.started_at || item.finished_at}`}>
                  <TableCell>{item.job}</TableCell>
                  <TableCell>{item.status}</TableCell>
                  <TableCell>{item.started_at ? formatDateTime(item.started_at) : "-"}</TableCell>
                  <TableCell>{item.finished_at ? formatDateTime(item.finished_at) : "-"}</TableCell>
                  <TableCell>{item.errors}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </GenericTable>
        </CardContent>
      </Card>
    </div>
  )
}

export function CacheManagementPage() {
  const [cleanupDays, setCleanupDays] = useState(7)
  const [confirm, setConfirm] = useState<ConfirmState>(null)
  const queryClient = useQueryClient()
  const statsQuery = useQuery({ queryKey: ["cache", "stats"], queryFn: () => getCacheStats(), retry: false })
  const detailsQuery = useQuery({ queryKey: ["cache", "details"], queryFn: () => getCacheDetails(1, 20), retry: false })
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
  const maxSize = stats?.maxSize || 1
  const usagePercent = Math.min(Math.round(((stats?.totalSize || 0) / maxSize) * 100), 100)

  return (
    <div>
      <PageHeader
        title="缓存管理"
        description="查看缓存统计、详情、后端信息并执行清理操作。"
        actions={<Button variant="outline" onClick={() => void statsQuery.refetch()}>刷新统计</Button>}
      />
      <div className="grid gap-4 md:grid-cols-4">
        <StatCard label="总文件数" value={stats?.totalFiles ?? 0} />
        <StatCard label="总大小" value={formatBytes(stats?.totalSize ?? 0)} />
        <StatCard label="股票数据" value={stats?.stockDataCount ?? 0} />
        <StatCard label="新闻数据" value={stats?.newsDataCount ?? 0} />
      </div>
      <Card className="mt-6">
        <CardHeader><CardTitle>缓存操作</CardTitle></CardHeader>
        <CardContent className="grid gap-4 md:grid-cols-3">
          <div className="rounded-md border p-4">
            <div className="text-sm font-medium">缓存使用率</div>
            <div className="mt-2 h-2 rounded bg-muted">
              <div className="h-2 rounded bg-primary" style={{ width: `${usagePercent}%` }} />
            </div>
            <div className="mt-2 text-xs text-muted-foreground">{usagePercent}% / {backendQuery.data?.primary_backend || "unknown"}</div>
          </div>
          <div className="flex gap-2">
            <Input type="number" min={1} max={30} value={cleanupDays} onChange={(event) => setCleanupDays(Number(event.target.value) || 7)} />
            <Button
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
          <Button
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
        </CardContent>
      </Card>
      <Card className="mt-6">
        <CardHeader><CardTitle>缓存详情</CardTitle></CardHeader>
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
                </TableRow>
              ))}
            </TableBody>
          </GenericTable>
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
        title="使用统计"
        description="查看 Token、成本、模型和供应商使用统计。"
        actions={
          <Select value={days} onValueChange={setDays}>
            <SelectTrigger className="w-32"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="7">最近7天</SelectItem>
              <SelectItem value="30">最近30天</SelectItem>
              <SelectItem value="90">最近90天</SelectItem>
            </SelectContent>
          </Select>
        }
      />
      <div className="grid gap-4 md:grid-cols-4">
        <StatCard label="总请求数" value={stats?.total_requests ?? 0} />
        <StatCard label="输入 Token" value={stats?.total_input_tokens ?? 0} />
        <StatCard label="输出 Token" value={stats?.total_output_tokens ?? 0} />
        <StatCard label="总成本" value={Object.entries(stats?.cost_by_currency || {}).map(([currency, value]) => `${value.toFixed(4)} ${currency}`).join(" / ") || "0"} />
      </div>
      <div className="mt-6 grid gap-4 lg:grid-cols-2">
        <EChartPanel option={providerOption} empty={!Object.keys(stats?.by_provider || {}).length} height={300} />
        <EChartPanel option={modelOption} empty={!Object.keys(stats?.by_model || {}).length} height={300} />
      </div>
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
                <TableHead>输入</TableHead>
                <TableHead>输出</TableHead>
                <TableHead>成本</TableHead>
                <TableHead>分析类型</TableHead>
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
  const [editingJob, setEditingJob] = useState<Job | null>(null)
  const [description, setDescription] = useState("")
  const [displayName, setDisplayName] = useState("")
  const queryClient = useQueryClient()
  const jobsQuery = useQuery({ queryKey: ["scheduler", "jobs"], queryFn: () => getJobs().then(getResponseData), retry: false })
  const statsQuery = useQuery({ queryKey: ["scheduler", "stats"], queryFn: () => getSchedulerStats().then(getResponseData), retry: false })
  const healthQuery = useQuery({ queryKey: ["scheduler", "health"], queryFn: () => getSchedulerHealth().then(getResponseData), retry: false })
  const actionMutation = useMutation({
    mutationFn: async (action: () => Promise<unknown>) => action(),
    onSuccess: () => {
      toast.success("调度任务已更新")
      void queryClient.invalidateQueries({ queryKey: ["scheduler"] })
      setEditingJob(null)
    },
    onError: (error) => toast.error(error.message)
  })

  const jobs = (jobsQuery.data || []).filter((job) => {
    const matchesKeyword = job.name.toLowerCase().includes(keyword.toLowerCase()) || (job.display_name || "").toLowerCase().includes(keyword.toLowerCase())
    const matchesStatus = status === "all" || (status === "running" ? !job.paused : job.paused)
    return matchesKeyword && matchesStatus
  })
  const stats = statsQuery.data
  const health = healthQuery.data

  return (
    <div>
      <PageHeader
        title="定时任务"
        description="管理调度任务、执行历史、任务健康和失败处理。"
        actions={<Button variant="outline" onClick={() => void jobsQuery.refetch()}>刷新</Button>}
      />
      <div className="grid gap-4 md:grid-cols-4">
        <StatCard label="总任务数" value={stats?.total_jobs ?? 0} />
        <StatCard label="运行中" value={stats?.running_jobs ?? 0} />
        <StatCard label="已暂停" value={stats?.paused_jobs ?? 0} />
        <StatCard label="调度器" value={health?.status || "unknown"} />
      </div>
      <Card className="mt-6">
        <CardHeader><CardTitle>筛选</CardTitle></CardHeader>
        <CardContent className="grid gap-3 md:grid-cols-3">
          <Input placeholder="搜索任务名称" value={keyword} onChange={(event) => setKeyword(event.target.value)} />
          <Select value={status} onValueChange={setStatus}>
            <SelectTrigger><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="all">全部状态</SelectItem>
              <SelectItem value="running">运行中</SelectItem>
              <SelectItem value="paused">已暂停</SelectItem>
            </SelectContent>
          </Select>
        </CardContent>
      </Card>
      <Card className="mt-6">
        <CardHeader><CardTitle>任务列表</CardTitle></CardHeader>
        <CardContent>
          <GenericTable<Job> rows={jobs} emptyText="暂无定时任务">
            <TableHeader>
              <TableRow>
                <TableHead>任务</TableHead>
                <TableHead>触发器</TableHead>
                <TableHead>下次执行</TableHead>
                <TableHead>状态</TableHead>
                <TableHead>操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {jobs.map((job) => (
                <TableRow key={job.id}>
                  <TableCell>
                    <div className="font-medium">{job.display_name || job.name}</div>
                    <div className="text-xs text-muted-foreground">{job.description || job.id}</div>
                  </TableCell>
                  <TableCell className="text-xs text-muted-foreground">{job.trigger}</TableCell>
                  <TableCell>{job.next_run_time ? formatDateTime(job.next_run_time) : "-"}</TableCell>
                  <TableCell>{boolBadge(!job.paused, "运行中", "已暂停")}</TableCell>
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
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </GenericTable>
        </CardContent>
      </Card>
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
    </div>
  )
}
