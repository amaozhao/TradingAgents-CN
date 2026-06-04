import { AppShell } from "@/components/layout/app-shell"
import { ProtectedRoute } from "@/components/layout/protected-route"
import { SystemLogsPage } from "@/features/settings/settings-pages"

export default function SettingsSystemLogsRoutePage() {
  return <ProtectedRoute><AppShell><SystemLogsPage /></AppShell></ProtectedRoute>
}
