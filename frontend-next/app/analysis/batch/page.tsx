import { AppShell } from "@/components/layout/app-shell"
import { ProtectedRoute } from "@/components/layout/protected-route"
import { BatchAnalysisPage } from "@/features/analysis/batch-analysis-page"

export default function AnalysisBatchPage() {
  return (
    <ProtectedRoute>
      <AppShell>
        <BatchAnalysisPage />
      </AppShell>
    </ProtectedRoute>
  )
}
