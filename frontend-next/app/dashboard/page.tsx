import { AppShell } from "@/components/layout/app-shell"
import { PlaceholderPage } from "@/components/layout/placeholder-page"
import { ProtectedRoute } from "@/components/layout/protected-route"

export default function DashboardPage() {
  return (
    <ProtectedRoute>
      <AppShell>
        <PlaceholderPage title="仪表板" />
      </AppShell>
    </ProtectedRoute>
  )
}
