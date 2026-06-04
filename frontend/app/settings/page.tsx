import { AppShell } from "@/components/layout/app-shell"
import { ProtectedRoute } from "@/components/layout/protected-route"
import { SettingsIndexPage } from "@/features/settings/settings-pages"

export default function SettingsRoutePage() {
  return <ProtectedRoute><AppShell><SettingsIndexPage /></AppShell></ProtectedRoute>
}
