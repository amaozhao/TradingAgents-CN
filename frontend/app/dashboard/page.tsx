import { AppShell } from "@/components/layout/app-shell"
import { ProtectedRoute } from "@/components/layout/protected-route"
import { ConfigWizard } from "@/features/config/config-wizard"
import { DashboardPage as DashboardFeature } from "@/features/dashboard/dashboard-page"

export default function DashboardPage() {
  return (
    <ProtectedRoute>
      <AppShell>
        <DashboardFeature />
        <ConfigWizard />
      </AppShell>
    </ProtectedRoute>
  )
}
