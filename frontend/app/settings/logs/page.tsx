import { AppShell } from "@/components/layout/app-shell"
import { ProtectedRoute } from "@/components/layout/protected-route"
import { OperationLogsPage } from "@/features/settings/settings-pages"

export default function SettingsLogsRoutePage() {
  return <ProtectedRoute><AppShell><OperationLogsPage /></AppShell></ProtectedRoute>
}
