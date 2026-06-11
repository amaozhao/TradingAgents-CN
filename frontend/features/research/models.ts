import type { LLMConfig } from "@/libs/api/config"

export function enabledModels(models: LLMConfig[]) {
  return models.filter((model) => model.enabled)
}

export function modelLabel(model: LLMConfig) {
  return model.model_display_name
    ? `${model.model_display_name} (${model.model_name})`
    : model.model_name
}

export function defaultStockModels(models: LLMConfig[]) {
  return {
    quick: models[0]?.model_name || "",
    deep: models[1]?.model_name || models[0]?.model_name || ""
  }
}
