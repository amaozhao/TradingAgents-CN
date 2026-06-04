import { AppShell } from "@/components/layout/app-shell"
import { ProtectedRoute } from "@/components/layout/protected-route"
import { ScreeningPage } from "@/features/screening/screening-page"

export default function ScreeningRoutePage() {
  return (
    <ProtectedRoute>
      <AppShell>
        <ScreeningPage />
      </AppShell>
    </ProtectedRoute>
  )
}
