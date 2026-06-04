import { AppShell } from "@/components/layout/app-shell"
import { ProtectedRoute } from "@/components/layout/protected-route"
import { SyncManagementPage } from "@/features/settings/settings-pages"

export default function SettingsSyncRoutePage() {
  return <ProtectedRoute><AppShell><SyncManagementPage /></AppShell></ProtectedRoute>
}
