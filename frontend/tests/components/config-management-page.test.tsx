import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { ConfigManagementPage } from "@/features/settings/settings-pages"
import { configApi } from "@/libs/api/config"

let routeSearch = ""
const replace = vi.fn()

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace }),
  useSearchParams: () => new URLSearchParams(routeSearch)
}))

vi.mock("@/libs/api/config", () => ({
  configApi: {
    getLLMProviders: vi.fn(),
    addLLMProvider: vi.fn(),
    updateLLMProvider: vi.fn(),
    deleteLLMProvider: vi.fn(),
    toggleLLMProvider: vi.fn(),
    migrateEnvToProviders: vi.fn(),
    initAggregatorProviders: vi.fn(),
    testProviderAPI: vi.fn(),
    getLLMConfigs: vi.fn(),
    updateLLMConfig: vi.fn(),
    deleteLLMConfig: vi.fn(),
    setDefaultLLM: vi.fn(),
    getDataSourceConfigs: vi.fn(),
    addDataSourceConfig: vi.fn(),
    updateDataSourceConfig: vi.fn(),
    deleteDataSourceConfig: vi.fn(),
    setDefaultDataSource: vi.fn(),
    getMarketCategories: vi.fn(),
    addMarketCategory: vi.fn(),
    updateMarketCategory: vi.fn(),
    deleteMarketCategory: vi.fn(),
    getDataSourceGroupings: vi.fn(),
    addDataSourceToCategory: vi.fn(),
    removeDataSourceFromCategory: vi.fn(),
    updateDataSourceGrouping: vi.fn(),
    getDatabaseConfigs: vi.fn(),
    addDatabaseConfig: vi.fn(),
    updateDatabaseConfig: vi.fn(),
    deleteDatabaseConfig: vi.fn(),
    testDatabaseConfig: vi.fn(),
    getSystemSettings: vi.fn(),
    getSystemSettingsMeta: vi.fn(),
    updateSystemSettings: vi.fn(),
    testConfig: vi.fn(),
    getModelCatalog: vi.fn(),
    saveModelCatalog: vi.fn(),
    deleteModelCatalog: vi.fn(),
    initModelCatalog: vi.fn(),
    validateSystemConfig: vi.fn(),
    exportConfig: vi.fn(),
    importConfig: vi.fn(),
    migrateLegacyConfig: vi.fn(),
    reloadConfig: vi.fn()
  }
}))

function renderWithQueryClient(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false }
    }
  })

  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>)
}

describe("ConfigManagementPage", () => {
  beforeEach(() => {
    routeSearch = ""
    replace.mockClear()
    vi.mocked(configApi.getLLMProviders).mockResolvedValue([
      { id: "dashscope", name: "dashscope", display_name: "通义千问", is_active: true, supported_features: ["chat"], extra_config: { has_api_key: true } }
    ])
    vi.mocked(configApi.getLLMConfigs).mockResolvedValue([
      { provider: "dashscope", model_name: "qwen-turbo", model_display_name: "通义千问 Turbo", max_tokens: 2000, temperature: 0.7, timeout: 60, retry_times: 2, enabled: true }
    ])
    vi.mocked(configApi.getDataSourceConfigs).mockResolvedValue([
      { name: "tushare", type: "stock", timeout: 30, rate_limit: 100, enabled: true, priority: 1, config_params: {}, display_name: "Tushare", market_categories: ["cn"] }
    ])
    vi.mocked(configApi.getMarketCategories).mockResolvedValue([
      { id: "cn", name: "cn", display_name: "A股", enabled: true, sort_order: 1 }
    ])
    vi.mocked(configApi.getDataSourceGroupings).mockResolvedValue([
      { data_source_name: "tushare", market_category_id: "cn", priority: 1, enabled: true }
    ])
    vi.mocked(configApi.getDatabaseConfigs).mockResolvedValue([
      { name: "default", type: "postgresql", host: "localhost", port: 5432, database: "agentrader", connection_params: {}, pool_size: 5, max_overflow: 10, enabled: true }
    ])
    vi.mocked(configApi.getSystemSettings).mockResolvedValue({
      default_data_source: "tushare",
      quick_analysis_model: "qwen-turbo",
      enable_cost_tracking: true,
      cost_alert_threshold: 100,
      log_level: "INFO"
    })
    vi.mocked(configApi.getSystemSettingsMeta).mockResolvedValue({ items: [] })
    vi.mocked(configApi.getModelCatalog).mockResolvedValue([
      { provider: "dashscope", provider_name: "通义千问", models: [{ name: "qwen-turbo", display_name: "通义千问 Turbo" }] }
    ])
    vi.mocked(configApi.validateSystemConfig).mockResolvedValue({
      success: true,
      env_validation: {
        success: true,
        missing_required: [],
        missing_recommended: [{ key: "TUSHARE_TOKEN", description: "Tushare 数据源 Token" }],
        invalid_configs: [],
        warnings: []
      },
      postgres_validation: {
        llm_providers: [{ name: "dashscope", display_name: "通义千问", is_active: true, has_api_key: true, status: "已配置" }],
        data_source_configs: [{ name: "akshare", type: "akshare", enabled: true, has_api_key: true, status: "已配置（无需密钥）" }],
        warnings: []
      }
    })
    vi.mocked(configApi.reloadConfig).mockResolvedValue({ success: true, message: "ok" })
    vi.mocked(configApi.testConfig).mockResolvedValue({ success: true, message: "ok" })
    vi.mocked(configApi.updateSystemSettings).mockResolvedValue({ message: "ok" })
    vi.mocked(configApi.exportConfig).mockResolvedValue({ message: "ok", data: { foo: "bar" }, exported_at: "2026-06-05T00:00:00Z" })
    vi.mocked(configApi.importConfig).mockResolvedValue({ message: "ok" })
    vi.mocked(configApi.migrateLegacyConfig).mockResolvedValue({ message: "ok" })
  })

  it("exposes the Vue config management control surface", async () => {
    const user = userEvent.setup()
    renderWithQueryClient(<ConfigManagementPage />)

    expect(await screen.findByRole("button", { name: "重载配置" })).toBeInTheDocument()
    expect(screen.getByRole("tab", { name: "配置验证" })).toBeInTheDocument()
    expect(screen.getByRole("tab", { name: "厂家管理" })).toBeInTheDocument()
    expect(screen.getByRole("tab", { name: "模型目录" })).toBeInTheDocument()
    expect(screen.getByRole("tab", { name: "大模型配置" })).toBeInTheDocument()
    expect(screen.getByRole("tab", { name: "数据源配置" })).toBeInTheDocument()
    expect(screen.getByRole("tab", { name: "数据库配置" })).toBeInTheDocument()
    expect(screen.getByRole("tab", { name: "API密钥状态" })).toBeInTheDocument()
    expect(screen.getByRole("tab", { name: "导入导出" })).toBeInTheDocument()
    expect(await screen.findByText("配置验证通过（有推荐配置未设置）")).toBeInTheDocument()

    await user.click(screen.getByRole("tab", { name: "厂家管理" }))
    expect(await screen.findByRole("button", { name: "编辑 dashscope" })).toBeInTheDocument()

    await user.click(screen.getByRole("tab", { name: "数据源配置" }))
    expect(await screen.findByRole("button", { name: "测试数据源 tushare" })).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "管理分组 tushare" })).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "新增分类" })).toBeInTheDocument()

    await user.click(screen.getByRole("tab", { name: "数据库配置" }))
    expect(await screen.findByRole("button", { name: "新增数据库" })).toBeInTheDocument()
    await user.click(screen.getByRole("button", { name: "编辑数据库 default" }))
    expect(screen.getByRole("dialog", { name: "编辑数据库配置" })).toBeInTheDocument()
  })

  it("saves editable system settings", async () => {
    const user = userEvent.setup()
    renderWithQueryClient(<ConfigManagementPage />)

    await user.click(await screen.findByRole("tab", { name: "系统设置" }))
    const quickModel = await screen.findByLabelText("快速分析模型")
    await user.clear(quickModel)
    await user.type(quickModel, "qwen-plus")
    await user.click(screen.getByRole("button", { name: "保存系统设置" }))

    await waitFor(() => expect(configApi.updateSystemSettings).toHaveBeenCalledWith(expect.objectContaining({ quick_analysis_model: "qwen-plus" })))
  })

  it("imports config json from the import/export tab", async () => {
    const user = userEvent.setup()
    renderWithQueryClient(<ConfigManagementPage />)

    await user.click(await screen.findByRole("tab", { name: "导入导出" }))
    const file = new File([JSON.stringify({ default_data_source: "akshare" })], "config.json", { type: "application/json" })
    await user.upload(screen.getByLabelText("导入配置文件"), file)
    await user.click(screen.getByRole("button", { name: "导入配置" }))

    await waitFor(() => expect(configApi.importConfig).toHaveBeenCalledWith({ default_data_source: "akshare" }))
  })

  it("opens the requested config tab from the URL", async () => {
    routeSearch = "tab=llm"
    renderWithQueryClient(<ConfigManagementPage />)

    expect(await screen.findByText("通义千问 Turbo")).toBeInTheDocument()
    expect(screen.getByRole("tab", { name: "大模型配置" })).toHaveAttribute("data-state", "active")
  })
})
