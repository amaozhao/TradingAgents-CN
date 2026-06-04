import { AppShell } from "@/components/layout/app-shell"
import { ProtectedRoute } from "@/components/layout/protected-route"
import { PaperTradingPage } from "@/features/paper/paper-trading-page"

export default function PaperRoutePage() {
  return (
    <ProtectedRoute>
      <AppShell>
        <PaperTradingPage />
      </AppShell>
    </ProtectedRoute>
  )
}
