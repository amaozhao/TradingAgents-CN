import { AppShell } from "@/components/layout/app-shell"
import { ProtectedRoute } from "@/components/layout/protected-route"
import { CacheManagementPage } from "@/features/settings/settings-pages"

export default function SettingsCacheRoutePage() {
  return <ProtectedRoute><AppShell><CacheManagementPage /></AppShell></ProtectedRoute>
}
