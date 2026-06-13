"use client"

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"

import { configApi } from "@/libs/api/config"

export function useConfigQueries() {
  return {
    databaseQuery: useQuery({ queryKey: ["config", "database"], queryFn: () => configApi.getDatabaseConfigs(), retry: false }),
    dataSourceQuery: useQuery({ queryKey: ["config", "datasources"], queryFn: () => configApi.getDataSourceConfigs(), retry: false }),
    groupingsQuery: useQuery({ queryKey: ["config", "datasource-groupings"], queryFn: () => configApi.getDataSourceGroupings(), retry: false }),
    llmQuery: useQuery({ queryKey: ["config", "llm"], queryFn: () => configApi.getLLMConfigs(), retry: false }),
    marketQuery: useQuery({ queryKey: ["config", "market-categories"], queryFn: () => configApi.getMarketCategories(), retry: false }),
    modelCatalogQuery: useQuery({ queryKey: ["config", "model-catalog"], queryFn: () => configApi.getModelCatalog(), retry: false }),
    providersQuery: useQuery({ queryKey: ["config", "llm-providers"], queryFn: () => configApi.getLLMProviders(), retry: false }),
    settingsMetaQuery: useQuery({ queryKey: ["config", "settings-meta"], queryFn: () => configApi.getSystemSettingsMeta(), retry: false }),
    settingsQuery: useQuery({ queryKey: ["config", "settings"], queryFn: () => configApi.getSystemSettings(), retry: false }),
    validationQuery: useQuery({ queryKey: ["config", "validation"], queryFn: () => configApi.validateSystemConfig(), retry: false })
  }
}

export function useConfigRefresh() {
  const queryClient = useQueryClient()
  return () => {
    void queryClient.invalidateQueries({ queryKey: ["config"] })
  }
}

export function useConfigActionMutation(refreshConfig: () => void) {
  return useMutation({
    mutationFn: async (action: () => Promise<unknown>) => action(),
    onSuccess: () => {
      toast.success("操作已完成")
      refreshConfig()
    },
    onError: (error) => toast.error(error.message)
  })
}
