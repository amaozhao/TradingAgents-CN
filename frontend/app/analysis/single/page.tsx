import { AppShell } from "@/components/layout/app-shell"
import { ProtectedRoute } from "@/components/layout/protected-route"
import { SingleAnalysisPage } from "@/features/analysis/single-analysis-page"

export default function AnalysisSinglePage() {
  return (
    <ProtectedRoute>
      <AppShell>
        <SingleAnalysisPage />
      </AppShell>
    </ProtectedRoute>
  )
}
