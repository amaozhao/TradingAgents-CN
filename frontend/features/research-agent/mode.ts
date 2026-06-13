export type ComposerMode = "chat" | "goal"

export type ResearchUiState = {
  composerMode: ComposerMode
  showStockConfig: boolean
  stockConfigSubmitted: boolean
  showBatchConfig: boolean
  batchConfigSubmitted: boolean
}

export type ResearchUiAction =
  | { type: "composer"; mode: ComposerMode }
  | { type: "openStock" }
  | { type: "openBatch" }
  | { type: "closeStock" }
  | { type: "closeBatch" }
  | { type: "closeConfigs" }
  | { type: "submitStock" }
  | { type: "submitBatch" }
  | { type: "reset" }

export const initialResearchUiState: ResearchUiState = {
  composerMode: "chat",
  showStockConfig: false,
  stockConfigSubmitted: false,
  showBatchConfig: false,
  batchConfigSubmitted: false
}

export function researchUiModeReducer(
  state: ResearchUiState,
  action: ResearchUiAction
): ResearchUiState {
  switch (action.type) {
    case "composer":
      return { ...state, composerMode: action.mode }
    case "openStock":
      return {
        composerMode: "chat",
        showStockConfig: true,
        stockConfigSubmitted: false,
        showBatchConfig: false,
        batchConfigSubmitted: false
      }
    case "openBatch":
      return {
        composerMode: "chat",
        showStockConfig: false,
        stockConfigSubmitted: false,
        showBatchConfig: true,
        batchConfigSubmitted: false
      }
    case "closeStock":
      return { ...state, showStockConfig: false, stockConfigSubmitted: false }
    case "closeBatch":
      return { ...state, showBatchConfig: false, batchConfigSubmitted: false }
    case "closeConfigs":
      return {
        ...state,
        showStockConfig: false,
        stockConfigSubmitted: false,
        showBatchConfig: false,
        batchConfigSubmitted: false
      }
    case "submitStock":
      return { ...state, stockConfigSubmitted: true }
    case "submitBatch":
      return { ...state, batchConfigSubmitted: true }
    case "reset":
      return initialResearchUiState
  }
}
