import { AppShell } from "@/components/layout/app-shell"
import { ProtectedRoute } from "@/components/layout/protected-route"
import { ReportsPage } from "@/features/reports/reports-page"

export default function ReportsRoutePage() {
  return (
    <ProtectedRoute>
      <AppShell>
        <ReportsPage />
      </AppShell>
    </ProtectedRoute>
  )
}
