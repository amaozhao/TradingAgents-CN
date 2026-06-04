import { AppShell } from "@/components/layout/app-shell"
import { ProtectedRoute } from "@/components/layout/protected-route"
import { ConfigManagementPage } from "@/features/settings/settings-pages"

export default function SettingsConfigRoutePage() {
  return <ProtectedRoute><AppShell><ConfigManagementPage /></AppShell></ProtectedRoute>
}
