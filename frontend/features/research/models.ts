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
  const quick = models[0]
  const deep = models.find((model) => model.provider === quick?.provider && model.model_name !== quick.model_name)
    || quick

  return {
    quick: quick?.model_name || "",
    deep: deep?.model_name || quick?.model_name || ""
  }
}
