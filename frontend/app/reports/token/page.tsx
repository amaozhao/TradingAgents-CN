import { AppShell } from "@/components/layout/app-shell"
import { ProtectedRoute } from "@/components/layout/protected-route"
import { TokenStatisticsPage } from "@/features/reports/token-statistics-page"

export default function ReportsTokenRoutePage() {
  return (
    <ProtectedRoute>
      <AppShell>
        <TokenStatisticsPage />
      </AppShell>
    </ProtectedRoute>
  )
}
