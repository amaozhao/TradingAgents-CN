import { AppShell } from "@/components/layout/app-shell"
import { ProtectedRoute } from "@/components/layout/protected-route"
import { UsageStatisticsPage } from "@/features/settings/settings-pages"

export default function SettingsUsageRoutePage() {
  return <ProtectedRoute><AppShell><UsageStatisticsPage /></AppShell></ProtectedRoute>
}
