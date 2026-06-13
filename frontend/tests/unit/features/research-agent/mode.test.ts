import { describe, expect, it } from "vitest"

import { initialResearchUiState, researchUiModeReducer } from "@/features/research-agent/mode"

describe("researchUiModeReducer", () => {
  it("keeps stock and batch configuration modes mutually exclusive", () => {
    const stockState = researchUiModeReducer(initialResearchUiState, { type: "openStock" })

    expect(stockState).toMatchObject({
      composerMode: "chat",
      showStockConfig: true,
      stockConfigSubmitted: false,
      showBatchConfig: false,
      batchConfigSubmitted: false
    })

    const batchState = researchUiModeReducer(stockState, { type: "openBatch" })

    expect(batchState).toMatchObject({
      composerMode: "chat",
      showStockConfig: false,
      stockConfigSubmitted: false,
      showBatchConfig: true,
      batchConfigSubmitted: false
    })
  })

  it("can close config cards without changing composer mode", () => {
    const goalState = researchUiModeReducer(
      researchUiModeReducer(initialResearchUiState, { type: "openStock" }),
      { type: "composer", mode: "goal" }
    )
    const closedState = researchUiModeReducer(goalState, { type: "closeConfigs" })

    expect(closedState.composerMode).toBe("goal")
    expect(closedState.showStockConfig).toBe(false)
    expect(closedState.showBatchConfig).toBe(false)
  })
})
