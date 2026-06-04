import { describe, expect, it } from "vitest"

import { analysisApi } from "@/libs/api/analysis"
import { authApi } from "@/libs/api/auth"
import { getCacheStats } from "@/libs/api/cache"
import { configApi } from "@/libs/api/config"
import { databaseApi } from "@/libs/api/database"
import { favoritesApi } from "@/libs/api/favorites"
import { LogsApi } from "@/libs/api/logs"
import { getDefaultModelConfigs } from "@/libs/api/model-capabilities"
import { getSupportedMarkets } from "@/libs/api/multi-market"
import { newsApi } from "@/libs/api/news"
import { notificationsApi } from "@/libs/api/notifications"
import OperationLogsApi from "@/libs/api/operation-logs"
import { paperApi } from "@/libs/api/paper"
import { getJobs } from "@/libs/api/scheduler"
import { screeningApi } from "@/libs/api/screening"
import { stockSyncApi } from "@/libs/api/stock-sync"
import { stocksApi } from "@/libs/api/stocks"
import { getDataSourcesStatus } from "@/libs/api/sync"
import { tagsApi } from "@/libs/api/tags"
import TemplatesApi from "@/libs/api/templates"
import { getUsageRecords } from "@/libs/api/usage"

describe("migrated API modules", () => {
  it("exports the Vue API surface from Next libs/api modules", () => {
    expect(analysisApi.startAnalysis).toBeTypeOf("function")
    expect(authApi.login).toBeTypeOf("function")
    expect(getCacheStats).toBeTypeOf("function")
    expect(configApi.getSystemConfig).toBeTypeOf("function")
    expect(databaseApi.getStatus).toBeTypeOf("function")
    expect(favoritesApi.list).toBeTypeOf("function")
    expect(LogsApi.listLogFiles).toBeTypeOf("function")
    expect(getDefaultModelConfigs).toBeTypeOf("function")
    expect(getSupportedMarkets).toBeTypeOf("function")
    expect(newsApi.getLatestNews).toBeTypeOf("function")
    expect(notificationsApi.getUnreadCount).toBeTypeOf("function")
    expect(OperationLogsApi.getOperationLogs).toBeTypeOf("function")
    expect(paperApi.getAccount).toBeTypeOf("function")
    expect(getJobs).toBeTypeOf("function")
    expect(screeningApi.run).toBeTypeOf("function")
    expect(stockSyncApi.syncSingle).toBeTypeOf("function")
    expect(stocksApi.getQuote).toBeTypeOf("function")
    expect(getDataSourcesStatus).toBeTypeOf("function")
    expect(tagsApi.list).toBeTypeOf("function")
    expect(TemplatesApi.list).toBeTypeOf("function")
    expect(getUsageRecords).toBeTypeOf("function")
  })
})
