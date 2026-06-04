import { AppShell } from "@/components/layout/app-shell"
import { ProtectedRoute } from "@/components/layout/protected-route"
import { DatabaseManagementPage } from "@/features/settings/settings-pages"

export default function SettingsDatabaseRoutePage() {
  return <ProtectedRoute><AppShell><DatabaseManagementPage /></AppShell></ProtectedRoute>
}
